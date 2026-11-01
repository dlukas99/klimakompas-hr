"""Generates docs/izvori-podataka.md and ATTRIBUTION.md from config/sources.yaml (SPEC §18)."""

from klimakompas.core.config import ROOT, Source, load_sources

ACCESS_TYPES = {
    "atom": "preuzimanje preko ATOM-a",
    "files": "preuzimanje datoteke",
    "wms_browser_only": "WMS samo u pregledniku korisnika",
    "rest": "REST API",
    "url_pattern": "XML datoteke po postaji",
    "wfs": "WFS",
    "cds": "Copernicus CDS API",
    "stac": "STAC API (čitanje prozorima)",
    "browser_style": "stil karte u pregledniku korisnika",
    "wms": "WMS",
    "landing_page": "stranica skupa",
}


def _clean(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def sources_markdown(sources: list[Source]) -> str:
    lines = [
        "# Izvori podataka",
        "",
        "Datoteku generira `kk docs sources` iz `config/sources.yaml`.",
        "",
        "| Skup | Izdavač | Pristup | Kadenca | Licenca | Koristi se za |",
        "|---|---|---|---|---|---|",
    ]
    for source in sources:
        name = f"[{source.name}]({source.landing_url})" if source.landing_url else source.name
        access = ACCESS_TYPES.get(str(source.access.get("type")), str(source.access.get("type")))
        lines.append(
            f"| {_clean(name)} | {_clean(source.publisher)} | {access} | "
            f"`{source.schedule or 'jednom'}` | {_clean(source.license)} | "
            f"{', '.join(source.used_for)} |"
        )
    return "\n".join(lines) + "\n"


def attribution_markdown(sources: list[Source]) -> str:
    lines = [
        "# Atribucije",
        "",
        "Datoteku generira `kk docs sources` iz `config/sources.yaml`.",
        "",
    ]
    lines += [f"- **{source.name}:** {source.attribution}" for source in sources]
    return "\n".join(lines) + "\n"


def write_source_docs() -> None:
    sources = load_sources()
    (ROOT / "docs" / "izvori-podataka.md").write_text(sources_markdown(sources), encoding="utf-8")
    (ROOT / "ATTRIBUTION.md").write_text(attribution_markdown(sources), encoding="utf-8")
