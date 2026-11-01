"""Derived datasets and the DCAT-AP catalogue (SPEC §15.3). OpenStreetMap is never included."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, PROV, XSD
from sqlalchemy import Engine

from klimakompas.core.config import ROOT, load_sources

EXPORT_DIR = ROOT / "data" / "export"
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
ODBL = "https://opendatacommons.org/licenses/odbl/1-0/"
# ADR 0003: datasets with values derived from the JRC flood maps follow the flood layer's licence.
FLOOD_DERIVED_LICENSE = ODBL
PUBLIC_BASE = "https://github.com/dlukas99/klimakompas-hr"
HR_AUTHORITY = "http://publications.europa.eu/resource/authority/country/HRV"
ENVI_THEME = "http://publications.europa.eu/resource/authority/data-theme/ENVI"
FORMATS = {
    "csv": ("text/csv", "http://publications.europa.eu/resource/authority/file-type/CSV"),
    "gpkg": (
        "application/geopackage+sqlite3",
        "http://publications.europa.eu/resource/authority/file-type/GPKG",
    ),
    "parquet": (
        "application/vnd.apache.parquet",
        "http://publications.europa.eu/resource/authority/file-type/PARQUET",
    ),
}
# Population below this is hidden in published cell data, as on the card.
DISCLOSURE_MIN = 10

CELLS_SQL = f"""
SELECT r.cell_id, c.jls_code, c.naselje_code, c.zupanija_code,
       CASE WHEN r.pop_total < {DISCLOSURE_MIN} THEN NULL ELSE r.pop_total END AS pop_total,
       r.h_flood, r.h_heat, r.h_fire, r.h_air, r.v_gen, r.v_heat, r.v_imputed,
       r.r_flood, r.r_heat, r.r_fire, r.r_air, r.ikr, r.ikr_class,
       r.class_flood, r.class_heat, r.class_fire, r.class_air, c.geom
FROM idx.current_risk_cell r JOIN ref.grid_1km c USING (cell_id)
ORDER BY r.cell_id
"""

JLS_SQL = """
SELECT r.jls_code, j.name, j.kind, z.name AS zupanija, r.pop, r.pop65, r.ikr_popw, r.ikr_class,
       r.rank_hr, r.rank_zup, r.exposed, j.geom
FROM idx.current_risk_jls r
JOIN ref.jls j ON j.code = r.jls_code
JOIN ref.zupanije z ON z.code = j.zupanija_code
ORDER BY r.rank_hr NULLS LAST
"""


@dataclass(frozen=True)
class Dataset:
    id: str
    title_hr: str
    title_en: str
    description_hr: str
    description_en: str
    license_url: str
    formats: tuple[str, ...]
    source_ids: tuple[str, ...]


ALL_SOURCES = (
    "jrc_efas_flood",
    "ecde",
    "landsat_lst",
    "esa_worldcover",
    "burnt_areas",
    "eea_pm25_1km",
    "dhmz_climate",
    "estat_census_grid_2021",
    "dzs_naselja_2021",
    "dgu_au",
)

DATASETS = (
    Dataset(
        "ikr-celije-1km",
        "Indeks klimatskog rizika po ćelijama od 1 km",
        "Climate Risk Index by 1 km grid cell",
        "Opasnosti, ranjivost, rizik i IKR za naseljene ćelije u Hrvatskoj.",
        "Hazards, vulnerability, risk and the index for populated cells in Croatia.",
        FLOOD_DERIVED_LICENSE,
        ("csv", "gpkg", "parquet"),
        ALL_SOURCES,
    ),
    Dataset(
        "ikr-jls",
        "Indeks klimatskog rizika po općinama i gradovima",
        "Climate Risk Index by municipality and town",
        "IKR ponderiran stanovništvom i rang za 556 jedinica lokalne samouprave.",
        "Population-weighted index and rank for 556 local government units.",
        FLOOD_DERIVED_LICENSE,
        ("csv", "gpkg"),
        ALL_SOURCES,
    ),
    Dataset(
        "izlozenost-jls",
        "Izloženost stanovništva po općinama i gradovima",
        "Population exposure by municipality and town",
        "Broj stanovnika i osoba 65+ u ćelijama razreda 4 ili 5, po opasnosti.",
        "People and people aged 65+ in cells of class 4 or 5, per hazard.",
        FLOOD_DERIVED_LICENSE,
        ("csv",),
        ALL_SOURCES,
    ),
)
EXPORT_FILES = {
    f"{dataset.id}.{extension}" for dataset in DATASETS for extension in dataset.formats
}


def exposure_table(jls: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in jls.itertuples():
        for hazard, values in row.exposed.items():
            rows.append(
                {
                    "jls_code": row.jls_code,
                    "name": row.name,
                    "hazard": hazard,
                    "pop_in_class_4_5": round(values["pop"]),
                    "pop65_in_class_4_5": round(values["pop65"]),
                    "share": round(values["share"], 4),
                }
            )
    return pd.DataFrame(rows)


def write_exports(engine: Engine, folder: Path = EXPORT_DIR) -> dict[str, int]:
    folder.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        cells = gpd.read_postgis(CELLS_SQL, conn, geom_col="geom", crs="EPSG:3035")
        jls = gpd.read_postgis(JLS_SQL, conn, geom_col="geom", crs="EPSG:3035")
    assert cells.crs is not None and cells.crs.to_epsg() == 3035
    assert jls.crs is not None and jls.crs.to_epsg() == 3035

    cells.drop(columns="geom").to_csv(folder / "ikr-celije-1km.csv", index=False)
    cells.to_file(folder / "ikr-celije-1km.gpkg", driver="GPKG", layer="ikr_celije")
    cells.drop(columns="geom").to_parquet(folder / "ikr-celije-1km.parquet", index=False)

    flat = jls.drop(columns=["exposed"])
    flat.drop(columns="geom").to_csv(folder / "ikr-jls.csv", index=False)
    flat.to_file(folder / "ikr-jls.gpkg", driver="GPKG", layer="ikr_jls")
    exposure_table(jls).to_csv(folder / "izlozenost-jls.csv", index=False)
    return {"cells": len(cells), "jls": len(jls)}


def build_catalog(public_url: str, issued: datetime | None = None) -> Graph:
    """DCAT-AP description of the derived datasets."""
    now = issued or datetime.now(UTC)
    base = public_url.rstrip("/")
    graph = Graph()
    graph.bind("dcat", DCAT)
    graph.bind("dct", DCTERMS)
    graph.bind("foaf", FOAF)
    graph.bind("prov", PROV)
    local = Namespace(f"{base}/api/v1/catalog#")
    publisher = BNode()
    graph.add((publisher, RDF.type, FOAF.Agent))
    graph.add((publisher, FOAF.name, Literal("Tim Požega, FERIT Osijek", lang="hr")))

    catalog = local["catalog"]
    graph.add((catalog, RDF.type, DCAT.Catalog))
    graph.add((catalog, DCTERMS.title, Literal("KlimaKompas HR – izvedeni skupovi", lang="hr")))
    graph.add((catalog, DCTERMS.title, Literal("KlimaKompas HR – derived datasets", lang="en")))
    graph.add(
        (
            catalog,
            DCTERMS.description,
            Literal("Izvedeni skupovi o klimatskom riziku u Hrvatskoj.", lang="hr"),
        )
    )
    graph.add((catalog, DCTERMS.publisher, publisher))
    graph.add((catalog, FOAF.homepage, URIRef(PUBLIC_BASE)))

    registry = {source.id: source for source in load_sources()}
    for dataset in DATASETS:
        subject = local[dataset.id]
        graph.add((catalog, DCAT.dataset, subject))
        graph.add((subject, RDF.type, DCAT.Dataset))
        graph.add((subject, DCTERMS.identifier, Literal(dataset.id)))
        graph.add((subject, DCTERMS.title, Literal(dataset.title_hr, lang="hr")))
        graph.add((subject, DCTERMS.title, Literal(dataset.title_en, lang="en")))
        graph.add((subject, DCTERMS.description, Literal(dataset.description_hr, lang="hr")))
        graph.add((subject, DCTERMS.description, Literal(dataset.description_en, lang="en")))
        graph.add((subject, DCTERMS.publisher, publisher))
        graph.add((subject, DCTERMS.spatial, URIRef(HR_AUTHORITY)))
        graph.add((subject, DCAT.theme, URIRef(ENVI_THEME)))
        graph.add((subject, DCTERMS.modified, Literal(now.date().isoformat(), datatype=XSD.date)))
        temporal = BNode()
        graph.add((temporal, RDF.type, DCTERMS.PeriodOfTime))
        graph.add((temporal, DCAT.startDate, Literal("2021-08-31", datatype=XSD.date)))
        graph.add((subject, DCTERMS.temporal, temporal))
        for source_id in dataset.source_ids:
            url = registry[source_id].landing_url
            if url:
                graph.add((subject, PROV.wasDerivedFrom, URIRef(url)))
        for extension in dataset.formats:
            media, file_type = FORMATS[extension]
            distribution = local[f"{dataset.id}.{extension}"]
            graph.add((subject, DCAT.distribution, distribution))
            graph.add((distribution, RDF.type, DCAT.Distribution))
            access = URIRef(f"{base}/api/v1/export/{dataset.id}.{extension}")
            graph.add((distribution, DCAT.accessURL, access))
            graph.add((distribution, DCAT.downloadURL, access))
            graph.add((distribution, DCAT.mediaType, Literal(media)))
            graph.add((distribution, DCTERMS.format, URIRef(file_type)))
            graph.add((distribution, DCTERMS.license, URIRef(dataset.license_url)))
    return graph


def write_catalog(public_url: str, folder: Path = EXPORT_DIR) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    graph = build_catalog(public_url)
    graph.serialize(folder / "catalog.ttl", format="turtle")
    (folder / "catalog.jsonld").write_text(
        json.dumps(json.loads(graph.serialize(format="json-ld")), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
