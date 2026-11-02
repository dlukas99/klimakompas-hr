"""Assistant mode for small models (ADR 0008): the LLM only reads the question.

A small model chose tools well but invented claims with no numbers in them, such as saying a
flooded place is not in a flood zone, which a numeric grounding check cannot catch. So here the
model only fills in a structured request, and all facts and wording come from tools and templates.
"""

import json
import re
import unicodedata
from collections.abc import Iterator
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection, text

from klimakompas.agent.grounding import check_answer
from klimakompas.agent.runner import AgentResult, LlmClient, LlmUnavailableError
from klimakompas.agent.tools import (
    tool_active_warnings,
    tool_air_quality,
    tool_jls_profile,
    tool_place_card,
    tool_rank_areas,
    tool_search_open_data,
)

PROMPT = (Path(__file__).parent / "prompts" / "intent_hr.md").read_text(encoding="utf-8")
MAX_INPUT_CHARS = 1000
MIN_NAME_SIMILARITY = 0.55
MIN_WORD_MATCH = 0.6
# A ranking or advice from the model counts only if the question really asks for one.
RANK_WORDS = ("koj", "gdje", "najv", "najg", "najm", "rang", "lista", "koliko")
ADVICE_WORDS = (
    "lijek",
    "zdrav",
    "lijec",
    "bolest",
    "pravn",
    "pravo",
    "novac",
    "financ",
    "smijem",
    "piti",
)
ADDRESS_CANDIDATES = 30
RANK_DEFAULT = 5

HAZARD_LABELS = {
    "ikr": "klimatskom riziku",
    "flood": "riziku od poplava",
    "heat": "toplinskom riziku",
    "fire": "riziku od požara",
    "air": "riziku od onečišćenja zraka",
}
CARD_HAZARD_KEYS = {"flood": "poplave", "heat": "toplina", "fire": "pozar", "air": "zrak"}
POLLUTANT_LABELS = {"pm25": "PM2,5", "pm10": "PM10", "no2": "NO₂", "o3": "O₃"}
OUT_OF_SCOPE = (
    "Mogu pomoći samo oko klimatskih rizika, okoliša i otvorenih podataka za mjesta u Hrvatskoj."
)
ADVICE = (
    "Ne dajem medicinske, pravne ni financijske savjete. Obratite se liječniku ili drugom "
    "stručnjaku. U hitnoj situaciji nazovite 112."
)
NO_DATA = (
    "Za to pitanje nemam podatak u izvorima koje koristim. Provjerite službene izvore ili stranicu "
    "Podaci."
)
NOT_UNDERSTOOD = "Nisam razumio pitanje. Pokušajte navesti mjesto i što vas zanima."


class Intent(BaseModel):
    intent: Literal[
        "place", "jls", "rank", "warnings", "air", "open_data", "out_of_scope", "advice", "no_data"
    ]
    place: str | None = None
    hazard: Literal["ikr", "flood", "heat", "fire", "air"] | None = None
    metric: Literal["risk", "pop_exposed", "pop65_exposed"] | None = None
    level: Literal["jls", "naselja"] | None = None
    zupanija: str | None = None
    jls: str | None = None
    station: str | None = None
    query: str | None = None
    limit: int | None = None


def parse_intent(content: str) -> Intent | None:
    """Only the intent has to be valid; a bad optional field is dropped, not fatal."""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        values = json.loads(match.group(0))
        if not isinstance(values, dict):
            return None
        for field in Intent.model_fields:
            if field != "intent" and field in values:
                try:
                    Intent(intent="no_data", **{field: values[field]})
                except ValidationError:
                    del values[field]
        return Intent.model_validate(values)
    except (ValueError, ValidationError):
        return None


def _mentions(question: str, words: tuple[str, ...]) -> bool:
    folded = _fold(question)
    return any(word in folded for word in words)


def _fold(value: str) -> str:
    text_value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return "".join(char for char in text_value if not unicodedata.combining(char))


def named_in_question(name: str, question: str) -> bool:
    """The model may not bring in a place the user did not mention. Allows Croatian case endings."""
    asked = re.findall(r"\w+", _fold(question))
    words = [word for word in re.findall(r"\w+", _fold(name)) if len(word) > 2 and word.isalpha()]
    return bool(words) and all(
        any(SequenceMatcher(None, word, token).ratio() >= MIN_WORD_MATCH for token in asked)
        for word in words
    )


def resolve_place(conn: Connection, name: str) -> dict[str, Any] | None:
    """A settlement or JLS whose name really matches, then an address. Never a loose guess."""
    row = conn.execute(
        text(
            """
            WITH q AS (SELECT ref.normalize_search(:name) AS value)
            SELECT label, kind, lat, lon, jls FROM (
                SELECT n.name AS label, 'settlement' AS kind,
                       ST_Y(ST_Transform(n.point, 4326)) AS lat,
                       ST_X(ST_Transform(n.point, 4326)) AS lon, j.name AS jls,
                       similarity(n.search_text, q.value) AS score, p.pop_total AS pop
                FROM ref.naselja n
                JOIN ref.jls j ON j.code = n.jls_code
                LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code, q
                WHERE n.search_text % q.value
                UNION ALL
                SELECT j.name, 'municipality', ST_Y(ST_Transform(ST_PointOnSurface(j.geom), 4326)),
                       ST_X(ST_Transform(ST_PointOnSurface(j.geom), 4326)), j.name,
                       similarity(j.search_text, q.value), 0
                FROM ref.jls j, q
                WHERE j.search_text % q.value
            ) candidates
            WHERE score >= :minimum
            ORDER BY score DESC, kind DESC, pop DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"name": name, "minimum": MIN_NAME_SIMILARITY},
    ).one_or_none()
    if row is not None:
        return dict(row._mapping)
    words = [word for word in re.split(r"[\s,]+", name) if word]
    if not any(len(word) >= 3 and word[0].isalpha() for word in words):
        return None
    normalized = conn.execute(
        text("SELECT ref.normalize_search(:name)"), {"name": " ".join(words)}
    ).scalar_one()
    tokens = normalized.split(" ")
    numbers = [token for token in tokens if token[0].isdigit()]
    patterns = [f"%{token}%" for token in tokens if token not in numbers]
    rows = conn.execute(
        text(
            """
            SELECT a.label, 'address' AS kind, ST_Y(ST_Transform(a.geom, 4326)) AS lat,
                   ST_X(ST_Transform(a.geom, 4326)) AS lon, j.name AS jls
            FROM ref.addresses a LEFT JOIN ref.jls j ON j.code = a.jls_code
            WHERE a.search_text LIKE ALL (:patterns)
              AND (cardinality(CAST(:numbers AS text[])) = 0
                   OR lower(a.house_number) = ANY (CAST(:numbers AS text[])))
            ORDER BY length(a.label)
            LIMIT :limit
            """
        ),
        {"patterns": patterns, "numbers": numbers, "limit": ADDRESS_CANDIDATES},
    ).all()
    towns = sorted({row.jls for row in rows if row.jls})
    if len(towns) > 1:
        return {"ambiguous": towns}
    return dict(rows[0]._mapping) if rows else None


def _hr(value: float | int, digits: int = 0) -> str:
    text_value = f"{value:,.{digits}f}"
    return text_value.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _hazard_sentence(name: str, block: dict[str, Any]) -> str:
    level = block["label"] or "bez razine"
    values = block["vrijednosti"]
    if name == "flood":
        if values.get("zone_return_period"):
            detail = f"točka je u zoni poplave 1:{values['zone_return_period']} godina (model JRC)"
        elif values.get("near_rp100"):
            detail = "točka je do 250 m od zone poplave 1:100 godina (model JRC)"
        else:
            detail = "točka je izvan modeliranih zona riječnih poplava (model JRC)"
        return f"Poplave: {level}; {detail}."
    if name == "heat":
        return (
            f"Toplina: {level}; vrući dani godišnje: oko {_hr(values['hot_days'] or 0)}, "
            f"tropske noći: oko {_hr(values['tropical_nights'] or 0)}."
        )
    if name == "fire":
        return (
            f"Požar: {level}; dani visoke opasnosti godišnje: oko {_hr(values['fwi_days'] or 0)}."
        )
    pm25 = values.get("pm25_annual")
    amount = f"; godišnji prosjek PM2,5 je {_hr(pm25, 1)} µg/m³" if pm25 is not None else ""
    return f"Zrak: {level}{amount}."


def _place_answer(
    conn: Connection, intent: Intent, place: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    result = tool_place_card(conn, place["lat"], place["lon"])
    data = result["data"]
    if "error" in data:
        return data["error"], result
    name = place["label"]
    where = f"{name} ({data['opcina_ili_grad']})" if place["jls"] != name else name
    lead = f"Za mjesto {where}" if place["kind"] != "address" else f"Za adresu {where}"
    risk = data["ukupni_rizik"]
    parts = []
    if risk["label"]:
        parts.append(
            f"{lead} ukupni klimatski rizik je {risk['label']}, veći od "
            f"{_hr(risk['veci_od_postotka_naseljenih_podrucja'], 0)} % naseljenih područja u "
            "Hrvatskoj [1]."
        )
    else:
        parts.append(f"{lead} nema stanovnika u ćeliji, pa se ukupni indeks ne računa [1].")
    selected = [intent.hazard] if intent.hazard in CARD_HAZARD_KEYS else list(CARD_HAZARD_KEYS)
    parts += [
        _hazard_sentence(hazard, data["opasnosti"][CARD_HAZARD_KEYS[hazard]]) + " [1]"
        for hazard in selected
    ]
    if intent.hazard in (None, "ikr") and place["kind"] == "municipality":
        parts.append(
            "Procjena vrijedi za jednu točku u općini; pregled cijele jedinice je na njezinoj "
            "stranici."
        )
    if place["kind"] == "settlement":
        parts.append("Procjena vrijedi za središnju točku naselja.")
    return " ".join(parts), result


def _jls_answer(conn: Connection, name: str) -> tuple[str, dict[str, Any]]:
    result = tool_jls_profile(conn, name)
    data = result["data"]
    if "error" in data:
        return f"Nisam pronašao općinu ili grad „{name}”.", result
    exposed = data["osobe_u_podrucjima_visokog_rizika"]
    labels = {"poplave": "poplave", "toplina": "toplina", "pozar": "požar", "zrak": "zrak"}
    listed = ", ".join(
        f"{labels[key]} {_hr(values['osobe'])}" for key, values in exposed.items() if key in labels
    )
    answer = (
        f"{data['name']} ({data['zupanija']}) ima {_hr(data['stanovnika'])} stanovnika, "
        f"od toga {_hr(data['stanovnika_65_plus'])} u dobi od 65 i više [1]. "
        f"Klimatski rizik je {data['label']}, rang {data['rang_u_hrvatskoj']} "
        f"od {data['od_ukupno']} u Hrvatskoj [1]. "
        f"Osobe u područjima visokog rizika, gornja procjena: {listed} [1]. "
        "Razredi su relativni, u odnosu na ostatak Hrvatske."
    )
    return answer, result


def _rank_answer(conn: Connection, intent: Intent) -> tuple[str, dict[str, Any]]:
    hazard = intent.hazard or "ikr"
    metric = intent.metric or "risk"
    if metric != "risk" and hazard == "ikr":
        hazard = "flood"
    level = intent.level or "jls"
    result = tool_rank_areas(
        conn,
        level=level,
        hazard=hazard,
        metric=metric,
        zupanija=intent.zupanija,
        jls=intent.jls,
        limit=intent.limit or RANK_DEFAULT,
    )
    rows = result["data"]
    if not isinstance(rows, list) or not rows:
        return NO_DATA, result
    if metric == "risk":
        listed = ", ".join(row.get("name") or row["naselje"] for row in rows)
        sentence = f"Najviše po {HAZARD_LABELS[hazard]}: {listed} [1]."
    else:
        who = "osoba 65+" if metric == "pop65_exposed" else "stanovnika"
        listed = ", ".join(
            f"{row.get('name') or row['naselje']} ({_hr(row['value'] or 0)})" for row in rows
        )
        sentence = (
            f"Najviše {who} u područjima visokog rizika ({HAZARD_LABELS[hazard]}): {listed} [1]. "
            "Brojevi su gornja procjena iz kilometarskih ćelija."
        )
    return f"{sentence} Razredi su relativni, u odnosu na ostatak Hrvatske.", result


def _warnings_answer(conn: Connection, intent: Intent) -> tuple[str, dict[str, Any]]:
    place = resolve_place(conn, intent.place) if intent.place else None
    known = place is not None and "ambiguous" not in place
    result = tool_active_warnings(
        conn,
        region=intent.zupanija,
        lat=place["lat"] if place and known else None,
        lon=place["lon"] if place and known else None,
    )
    rows = result["data"]
    if not rows:
        return "Trenutno nema aktivnih upozorenja DHMZ-a za to područje [1].", result
    events = sorted({row["event"] for row in rows if row["event"]})
    areas = sorted({row["area"] for row in rows if row["area"]})
    shown = ", ".join(areas[:6]) + (" i druga područja" if len(areas) > 6 else "")
    return f"Aktivna upozorenja DHMZ-a: {'; '.join(events)}. Područja: {shown} [1].", result


def _air_answer(conn: Connection, intent: Intent) -> tuple[str, dict[str, Any]]:
    if intent.station:
        result = tool_air_quality(conn, station=intent.station)
        data = result["data"]
        if isinstance(data, dict) and "error" in data:
            place = resolve_place(conn, intent.station)
            if place is None or "ambiguous" in place:
                return f"{data['error']}.", result
        else:
            station = data[0]
            values = [
                f"{POLLUTANT_LABELS[name]} {_hr(item['value'], 1)} µg/m³ ({item['eaqi_label']})"
                for name, item in station["values"].items()
                if not item["stale"]
            ]
            if not values:
                return f"Postaja {station['name']} nema svježih mjerenja [1].", result
            return f"Na postaji {station['name']} sada: {', '.join(values)} [1].", result
    name = intent.place or intent.station
    place = resolve_place(conn, name) if name else None
    if place is None or "ambiguous" in place:
        return "Navedite mjesto ili postaju za koju vas zanima kvaliteta zraka.", {"sources": []}
    result = tool_air_quality(conn, lat=place["lat"], lon=place["lon"])
    data = result["data"]
    if "error" in data:
        return f"{data['error']} Provjerite iszz.azo.hr.", result
    pollutant = "PM2,5" if data["pollutant"] == "pm25" else "PM10"
    value = data["value"]
    lead = (
        ""
        if data["substitution"] == "local"
        else "U blizini nema svježeg PM2,5, pa je prikazana zamjena. "
    )
    answer = (
        f"{lead}Na postaji {data['station']['name']} "
        f"({_hr(data['station']['distance_km'], 1)} km) {pollutant} iznosi "
        f"{_hr(value['value'], 1)} µg/m³, što je razina „{value['eaqi_label']}” [1]."
    )
    return answer, result


def _open_data_answer(conn: Connection, intent: Intent) -> tuple[str, dict[str, Any]]:
    result = tool_search_open_data(conn, intent.query or "klima")
    data = result["data"]
    if "error" in data:
        return data["error"], result
    if not data["results"]:
        return "Na Portalu otvorenih podataka nema skupova za taj pojam [1].", result
    listed = "; ".join(item["title"] for item in data["results"][:5])
    count = _hr(data["count"])
    return f"Broj skupova na Portalu za taj pojam: {count} [1]. Primjeri: {listed}.", result


def run_structured(
    conn: Connection, llm: LlmClient | None, question: str
) -> Iterator[dict[str, Any]]:
    """Same events as the tool loop: progress first, then one final answer.

    Without a model, or when it does not answer, the question is read by fixed rules.
    """
    from klimakompas.agent.rules import parse_rules

    question = question[:MAX_INPUT_CHARS]
    intent: Intent | None = None
    if llm is not None:
        try:
            message = llm.chat(
                [{"role": "system", "content": PROMPT}, {"role": "user", "content": question}],
                use_tools=False,
            )
            intent = parse_intent(message.get("content") or "")
        except LlmUnavailableError:
            intent = None
    if intent is None:
        intent = parse_rules(conn, question)
    if intent is not None and (
        (intent.intent == "rank" and not _mentions(question, RANK_WORDS))
        or (intent.intent == "advice" and not _mentions(question, ADVICE_WORDS))
    ):
        intent = Intent(intent="out_of_scope")
    tools: list[str] = []
    actions: list[dict[str, Any]] = []
    result: dict[str, Any] = {"data": None, "sources": []}
    if intent is None:
        answer = NOT_UNDERSTOOD
    elif intent.intent == "out_of_scope":
        answer = OUT_OF_SCOPE
    elif intent.intent == "advice":
        answer = ADVICE
    elif intent.intent == "no_data":
        answer = NO_DATA
    elif intent.intent == "jls":
        name = intent.jls or intent.place or ""
        if not named_in_question(name, question):
            answer = "Navedite općinu ili grad koji vas zanima."
        else:
            yield {"event": "tool", "name": "get_jls_profile"}
            tools.append("get_jls_profile")
            answer, result = _jls_answer(conn, name)
            data = result.get("data") or {}
            if "lat" in data:
                actions = [
                    {"type": "show", "lat": data["lat"], "lon": data["lon"], "label": data["name"]}
                ]
    elif intent.intent == "place":
        yield {"event": "tool", "name": "geocode"}
        tools.append("geocode")
        known = bool(intent.place) and named_in_question(intent.place or "", question)
        place = resolve_place(conn, intent.place or "") if known else None
        if place is None:
            answer = "Nisam pronašao to mjesto u Hrvatskoj. Provjerite naziv ili upišite adresu."
        elif "ambiguous" in place:
            towns = ", ".join(place["ambiguous"][:6])
            answer = f"Ta adresa postoji u više mjesta: {towns}. Navedite i mjesto."
        else:
            yield {"event": "tool", "name": "get_place_card"}
            tools.append("get_place_card")
            answer, result = _place_answer(conn, intent, place)
            actions = [
                {"type": "show", "lat": place["lat"], "lon": place["lon"], "label": place["label"]}
            ]
    elif intent.intent == "rank":
        yield {"event": "tool", "name": "rank_areas"}
        tools.append("rank_areas")
        answer, result = _rank_answer(conn, intent)
    elif intent.intent == "warnings":
        yield {"event": "tool", "name": "get_active_warnings"}
        tools.append("get_active_warnings")
        answer, result = _warnings_answer(conn, intent)
    elif intent.intent == "air":
        yield {"event": "tool", "name": "get_air_quality"}
        tools.append("get_air_quality")
        answer, result = _air_answer(conn, intent)
    else:
        yield {"event": "tool", "name": "search_open_data"}
        tools.append("search_open_data")
        answer, result = _open_data_answer(conn, intent)

    sources = result.get("sources", [])
    check = check_answer(answer, [result.get("data")], question)
    yield {
        "event": "answer",
        "result": AgentResult(
            text=answer,
            citations=[{"n": n, **source} for n, source in enumerate(sources, start=1)],
            map_actions=actions,
            grounded=check.ok,
            tools_used=tools,
            numbers_total=check.total,
            numbers_ungrounded=len(check.ungrounded),
        ),
    }
