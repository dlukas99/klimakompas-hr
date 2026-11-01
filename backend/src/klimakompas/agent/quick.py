"""Quick questions without an LLM (SPEC §10.7): fixed queries and templates with citations."""

from typing import Any, Literal

from sqlalchemy import Connection

from klimakompas.agent.tools import (
    tool_active_warnings,
    tool_air_quality,
    tool_rank_areas,
    tool_search_open_data,
)

QuickId = Literal["older_exposed", "hottest", "air_near", "warnings", "flood_data"]
FLOOD_QUERY = "poplave"
TOP = 5


def _hr(value: float, digits: int = 0) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _citations(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"n": n, **source} for n, source in enumerate(result.get("sources", []), start=1)]


def _answer(text: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"text": text, "citations": _citations(result), "as_of": result.get("as_of")}


def quick_answer(
    conn: Connection,
    question: QuickId,
    jls: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    if question == "older_exposed":
        if not jls:
            return {"text": "Odaberite općinu ili grad.", "citations": [], "as_of": None}
        result = tool_rank_areas(
            conn, level="naselja", hazard="heat", metric="pop65_exposed", jls=jls, limit=TOP
        )
        rows = [row for row in result["data"] if row["value"]]
        if not rows:
            return _answer(
                "U ovoj općini ili gradu nema osoba 65+ u zonama visokog toplinskog rizika.", result
            )
        listed = "; ".join(f"{row['naselje']}: {_hr(row['value'])}" for row in rows)
        return _answer(
            f"Naselja s najviše osoba 65+ u ćelijama visokog toplinskog rizika: {listed} [1]. "
            "Brojevi su gornja procjena iz ćelija od 1 km.",
            result,
        )
    if question == "hottest":
        if not jls:
            return {"text": "Odaberite općinu ili grad.", "citations": [], "as_of": None}
        result = tool_rank_areas(
            conn, level="naselja", hazard="heat", metric="risk", jls=jls, limit=TOP
        )
        rows = [row for row in result["data"] if row["value"] is not None]
        if not rows:
            return _answer("Za ovu općinu ili grad nema podataka o toplini.", result)
        listed = "; ".join(f"{row['naselje']}: {_hr(row['value'], 2)}" for row in rows)
        return _answer(
            f"Naselja s najvišim toplinskim rizikom (ljestvica 0–1): {listed} [1]. "
            "To je položaj u odnosu na ostatak Hrvatske.",
            result,
        )
    if question == "air_near":
        if lat is None or lon is None:
            return {
                "text": "Odaberite lokaciju na karti ili pretragom.",
                "citations": [],
                "as_of": None,
            }
        result = tool_air_quality(conn, lat=lat, lon=lon)
        data = result["data"]
        if "error" in data:
            return _answer(f"{data['error']} Provjerite iszz.azo.hr.", result)
        name = "PM2,5" if data["pollutant"] == "pm25" else "PM10"
        value = data["value"]
        lead = (
            ""
            if data["substitution"] == "local"
            else "U blizini nema svježeg PM2,5, pa je prikazana zamjena. "
        )
        return _answer(
            f"{lead}Na postaji {data['station']['name']} "
            f"({_hr(data['station']['distance_km'], 1)} km) "
            f"{name} iznosi {_hr(value['value'], 1)} µg/m³, "
            f"što je razina „{value['eaqi_label']}” [1].",
            result,
        )
    if question == "warnings":
        result = tool_active_warnings(conn, lat=lat, lon=lon)
        rows = result["data"]
        if not rows:
            return _answer("Trenutno nema aktivnih upozorenja DHMZ-a za ovo područje [1].", result)
        events = sorted({row["event"] for row in rows if row["event"]})
        areas = sorted({row["area"] for row in rows if row["area"]})[:6]
        return _answer(
            f"Aktivna upozorenja DHMZ-a: {', '.join(events)}. Područja: {', '.join(areas)} [1].",
            result,
        )
    result = tool_search_open_data(conn, FLOOD_QUERY)
    data = result["data"]
    if "error" in data:
        return _answer(data["error"], result)
    listed = "; ".join(f"{item['title']} ({item['publisher']})" for item in data["results"])
    return _answer(
        f"Na Portalu ima {_hr(data['count'])} skupova za pojam „poplave” [1]. "
        f"Prvih nekoliko: {listed}.",
        result,
    )
