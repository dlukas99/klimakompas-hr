"""Reads a Croatian question without a language model, so free questions work on any server.

It fills the same structured request as the model (ADR 0008), so answers still come only from tools.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import Connection, text

from klimakompas.agent.structured import Intent

MIN_RATIO = 0.75
# Croatian drops a vowel in some cases (Zadar, Zadru; Sisak, Sisku), so only 3 letters are fixed.
STEM = 3
NUMBER_WORDS = {"dva": 2, "dvije": 2, "tri": 3, "cetiri": 4, "pet": 5, "sest": 6, "deset": 10}

HAZARD_WORDS = {
    "flood": ("poplav", "rijek", "nasip", "izlije", "bujic"),
    "heat": ("toplin", "vruc", "vrucin", "tropsk", "temperatur", "toplih", "topli", "zeg"),
    "fire": ("pozar", "vatr", "gori", "opozar"),
    "air": ("zrak", "pm2", "pm10", "prasin", "oneciscen", "zagaden", "smog"),
}
ADVICE = ("lijek", "zdrav", "lijecn", "bolest", "pravn", "odvjetn", "novac", "kredit", "osigura")
NO_DATA = (
    "poginu",
    "zrtv",
    "umrl",
    "stet",
    "kosta",
    "cijen",
    "stradal",
    "osteceno",
    "prosle godine",
)
WARNINGS = (
    "upozoren",
    "nevrijem",
    "oluj",
    "alarm",
    "meteoalarm",
    "opasnog vremen",
    "opasno vrijeme",
)
OPEN_DATA = ("otvoren", "portal", "data.gov", "skupov", "skup podataka", "dataset")
STREET_BREAKS = {
    "adresi",
    "adresa",
    "adresu",
    "ulici",
    "rizici",
    "rizicima",
    "kakvi",
    "su",
    "sto",
    "s",
    "kod",
}
TOPIC_NOISE = ("podac", "podatak", "postoj", "otvoren", "portal", "data", "skup", "nac", "mogu")
AIR_NOW = ("sada", "danas", "trenutno", "postaj", "trcat", "disat", "setat", "kvaliteta zraka")
RANK = (
    "koje opcin",
    "koji grad",
    "koja naselj",
    "koje jedinic",
    "gdje je najv",
    "gdje zivi",
    "najvis",
    "najvec",
    "najgor",
    "rang list",
    "navedi",
    "popis opcin",
    "top ",
)
JLS_PROFILE = (
    "koliko stanovnik",
    "koliko ljudi",
    "broj stanovnik",
    "koji je rang",
    "rang ",
    "profil",
    "pregled",
)
SENIORS = ("starij", "65", "umirovljen", "stari ")
PEOPLE = ("stanovnik", "ljud", "osob", "zivi", "izlozen")
STOP = {
    "u",
    "na",
    "za",
    "je",
    "li",
    "i",
    "s",
    "sa",
    "od",
    "do",
    "o",
    "mi",
    "me",
    "se",
    "koliko",
    "kakav",
    "kakva",
    "kakvo",
    "koji",
    "koja",
    "koje",
    "gdje",
    "ima",
    "imaju",
    "rizik",
    "opasnost",
    "grad",
    "opcina",
    "opcinu",
    "grada",
    "mjesto",
    "mjestu",
    "naselje",
    "adresa",
    "adresi",
    "zupanija",
    "zupaniji",
    "hrvatska",
    "hrvatskoj",
}


def fold(value: str) -> str:
    folded = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def _has(text_value: str, words: tuple[str, ...]) -> bool:
    return any(word in text_value for word in words)


def _same_word(asked: str, name: str) -> bool:
    """Croatian case endings change the end of a name: Osijek, Osijeku; Rijeka, Rijeci.

    The beginning must match exactly, so a different word that merely looks similar never counts.
    """
    if asked == name:
        return True
    if len(name) < STEM + 1 or asked[:STEM] != name[:STEM] or abs(len(asked) - len(name)) > 3:
        return False
    return SequenceMatcher(None, asked, name).ratio() >= MIN_RATIO


@dataclass(frozen=True)
class Name:
    words: tuple[str, ...]
    kind: str
    label: str
    population: int


_NAMES: dict[str, tuple[Name, ...]] = {}


def load_names(conn: Connection) -> tuple[Name, ...]:
    """Settlement, JLS and county names, loaded once per process."""
    if "all" not in _NAMES:
        rows = conn.execute(
            text(
                """
                SELECT n.name, 'settlement' AS kind, coalesce(p.pop_total, 0) AS pop
                FROM ref.naselja n LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code
                UNION ALL
                SELECT j.name, 'municipality', coalesce(p.pop_total, 0)
                FROM ref.jls j LEFT JOIN pop.jls_2021 p ON p.jls_code = j.code
                UNION ALL
                SELECT regexp_replace(z.name, ' županija$', ''), 'county', 0 FROM ref.zupanije z
                """
            )
        )
        _NAMES["all"] = tuple(
            Name(tuple(re.findall(r"\w+", fold(row.name))), row.kind, row.name, row.pop)
            for row in rows
        )
    return _NAMES["all"]


def find_names(conn: Connection, question: str) -> list[Name]:
    """Names in the question, longest first. When the user writes capitals at all, a name must be
    capitalised, so "rijeka" as a river is not taken for the town of Rijeka. The first word of the
    question is only taken when it is exactly a name, since questions start with a capital."""
    original = re.findall(r"\w+", question)
    tokens = [fold(word) for word in original]
    uses_capitals = any(word[:1].isupper() for word in original[1:])
    found: list[tuple[int, int, Name]] = []
    for name in load_names(conn):
        size = len(name.words)
        if not size or (size == 1 and len(name.words[0]) < 3):
            continue
        for start in range(len(tokens) - size + 1):
            window = tokens[start : start + size]
            if window[0] in STOP:
                continue
            if uses_capitals and not original[start][:1].isupper():
                continue
            if start == 0 and window != list(name.words):
                continue
            if all(_same_word(asked, part) for asked, part in zip(window, name.words, strict=True)):
                found.append((size, name.population, name))
    found.sort(key=lambda item: (item[0], item[2].kind != "county", item[1]), reverse=True)
    return [name for _, _, name in found]


def _address(question: str, town: str | None) -> str | None:
    """A street and house number, such as "Trg slobode 7", plus the town if one is named.

    Street names mix capitals and small letters, so words are collected back from the number
    until a word that cannot be part of a street, such as "adresi" or "u".
    """
    words = re.findall(r"[\w.\-]+%?", question)
    for position, word in enumerate(words):
        if not re.fullmatch(r"\d{1,4}[a-zA-Z]?", word) or position == 0:
            continue
        street: list[str] = []
        for previous in reversed(words[max(0, position - 5) : position]):
            if fold(previous) in STOP or fold(previous) in STREET_BREAKS:
                break
            street.insert(0, previous)
        if street and any(part[:1].isupper() for part in street) and len(street[-1]) >= 3:
            return " ".join([*street, word, town or ""]).strip()
    return None


def _limit(folded: str) -> int | None:
    digits = re.search(r"\b(\d{1,2})\b", folded)
    if digits and not re.search(r"pm\s?(2|10)", folded):
        return int(digits.group(1))
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", folded):
            return value
    return None


def parse_rules(conn: Connection, question: str) -> Intent:
    folded = fold(question)
    names = find_names(conn, question)
    counties = [name for name in names if name.kind == "county"]
    # "Šibensko-kninska" names a county, so it must not also be read as the town of Šibenik.
    county_stems = {word[:STEM] for county in counties for word in county.words}
    places = [
        name for name in names if name.kind != "county" and name.words[0][:STEM] not in county_stems
    ]
    place = places[0].label if places else None
    # Place names must not count as hazard words: "Rijeka-2" is a station, not a river.
    without_names = folded
    for name in names:
        for word in name.words:
            without_names = re.sub(rf"\b{re.escape(word[:STEM])}\w*", " ", without_names)
    hazard = next(
        (name for name, words in HAZARD_WORDS.items() if _has(without_names, words)), None
    )
    station = re.search(r"postaj\w*\s+([\w\-]+(?:\s*-\s*\d)?)", question, re.IGNORECASE)

    if _has(folded, ADVICE):
        return Intent(intent="advice")
    if _has(folded, NO_DATA):
        return Intent(intent="no_data")
    if _has(folded, WARNINGS):
        return Intent.model_validate(
            {
                "intent": "warnings",
                "place": place,
                "zupanija": counties[0].label if counties else None,
            }
        )
    if _has(folded, OPEN_DATA):
        words = [word for word in re.findall(r"\w+", without_names) if len(word) > 3]
        topic = [word for word in words if word not in STOP and not _has(word, TOPIC_NOISE)]
        return Intent(intent="open_data", query=" ".join(topic[:3]) or None)
    if station:
        return Intent(intent="air", station=station.group(1))
    if hazard == "air" and _has(folded, AIR_NOW) and "prosje" not in folded:
        return Intent(intent="air", place=_address(question, place) or place)
    if _has(folded, RANK):
        if _has(folded, SENIORS):
            metric = "pop65_exposed"
        elif _has(folded, PEOPLE):
            metric = "pop_exposed"
        else:
            metric = "risk"
        return Intent.model_validate(
            {
                "intent": "rank",
                "hazard": hazard or "ikr",
                "metric": metric,
                "level": "naselja" if "naselj" in folded else "jls",
                "zupanija": counties[0].label if counties else None,
                "jls": place,
                "limit": _limit(folded),
            }
        )
    if place and _has(folded, JLS_PROFILE) and hazard is None:
        return Intent(intent="jls", jls=place)
    address = _address(question, place)
    if address or place:
        return Intent.model_validate(
            {"intent": "place", "place": address or place, "hazard": hazard}
        )
    if re.search(r"\b(mjest\w*|grad\w*|opcin\w*|naselj\w*)\s+[A-ZČĆĐŠŽ]", question):
        # The user named a place we do not have; say so instead of answering for all of Croatia.
        return Intent(intent="place", place=question)
    if hazard and _has(folded, ("gdje", "koj", "najv")):
        return Intent.model_validate(
            {"intent": "rank", "hazard": hazard, "metric": "risk", "level": "jls"}
        )
    return Intent(intent="out_of_scope")
