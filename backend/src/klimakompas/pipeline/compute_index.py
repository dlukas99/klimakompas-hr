"""`kk index compute`: read the hazard tables, write one idx run and refresh the tile views."""

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog
from sqlalchemy import Connection, text

from klimakompas.core.config import ROOT, load_index_config, load_thresholds
from klimakompas.core.db import upsert_rows
from klimakompas.pipeline.index import (
    HAZARDS,
    CellInputs,
    aggregate_cells,
    competition_ranks,
    compute_cell_index,
    config_hash,
    quintile_classes,
)

log = structlog.get_logger()

KEEP_RUNS = 3

CELLS_SQL = """
SELECT g.cell_id, g.pop_total, g.share_ge65, g.share_lt15,
       c.jls_code, c.naselje_code, j.zupanija_code,
       g.age_share_source, l.tree_share,
       f.h_flood, h.h_heat, x.h_fire, a.h_air, a.pm25_annual
FROM pop.grid_2021 g
JOIN ref.grid_1km c USING (cell_id)
JOIN ref.jls j ON j.code = c.jls_code
LEFT JOIN haz.landcover_cell l USING (cell_id)
LEFT JOIN haz.flood_cell f USING (cell_id)
LEFT JOIN haz.heat_cell h USING (cell_id)
LEFT JOIN haz.fire_cell x USING (cell_id)
LEFT JOIN haz.air_cell a USING (cell_id)
WHERE g.pop_total >= :min_pop
ORDER BY g.cell_id
"""


def _floats(rows: list[Any], name: str) -> np.ndarray:
    return np.array([getattr(row, name) for row in rows], dtype=float)


def _none(value: float) -> float | None:
    return None if np.isnan(value) else float(value)


def _class(value: int) -> int | None:
    return int(value) if value > 0 else None


def compute_index(conn: Connection) -> int:
    config = load_index_config()
    thresholds = load_thresholds()
    config_dir = ROOT / "config"
    sha = config_hash(
        (config_dir / "index.yaml").read_text(encoding="utf-8"),
        (config_dir / "thresholds.yaml").read_text(encoding="utf-8"),
    )
    started = datetime.now(UTC)
    versions = {
        row.source_id: row.last_success_at.isoformat() if row.last_success_at else None
        for row in conn.execute(text("SELECT source_id, last_success_at FROM meta.sources"))
    }
    run_id: int = conn.execute(
        text(
            "INSERT INTO idx.runs (index_version, config_sha, started_at, status, "
            "source_versions) VALUES (:version, :sha, :started, 'running', "
            "CAST(:versions AS jsonb)) RETURNING run_id"
        ),
        {
            "version": f"{config['version']}+{sha[:8]}",
            "sha": sha,
            "started": started,
            "versions": json.dumps(versions),
        },
    ).scalar_one()

    rows = list(conn.execute(text(CELLS_SQL), {"min_pop": config["populated_min_pop"]}))
    if not rows:
        raise ValueError("no populated cells: load the population grid first")

    hazards = {name: _floats(rows, f"h_{name}") for name in HAZARDS}
    inputs = CellInputs(
        pop_total=np.array([row.pop_total for row in rows], dtype=np.int32),
        share_ge65=_floats(rows, "share_ge65"),
        share_lt15=_floats(rows, "share_lt15"),
        tree_share=_floats(rows, "tree_share"),
        h=hazards,
        pm25=_floats(rows, "pm25_annual"),
    )
    index = compute_cell_index(inputs, config, thresholds["pm25_annual_ugm3"]["card_levels"])

    upsert_rows(
        conn,
        "idx.risk_cell",
        (
            "run_id",
            "cell_id",
            "pop_total",
            "h_flood",
            "h_heat",
            "h_fire",
            "h_air",
            "v_gen",
            "v_heat",
            "v_imputed",
            "r_flood",
            "r_heat",
            "r_fire",
            "r_air",
            "ikr",
            "ikr_class",
            "class_flood",
            "class_heat",
            "class_fire",
            "class_air",
        ),
        ("run_id", "cell_id"),
        (
            (
                run_id,
                row.cell_id,
                int(inputs.pop_total[i]),
                _none(hazards["flood"][i]),
                _none(hazards["heat"][i]),
                _none(hazards["fire"][i]),
                _none(hazards["air"][i]),
                _none(index.v_gen[i]),
                _none(index.v_heat[i]),
                row.age_share_source != "cell",
                _none(index.r["flood"][i]),
                _none(index.r["heat"][i]),
                _none(index.r["fire"][i]),
                _none(index.r["air"][i]),
                _none(index.ikr[i]),
                _class(index.ikr_class[i]),
                _class(index.classes["flood"][i]),
                _class(index.classes["heat"][i]),
                _class(index.classes["fire"][i]),
                _class(index.classes["air"][i]),
            )
            for i, row in enumerate(rows)
        ),
    )

    high = int(config["exposure"]["high_class_min"])
    pop = inputs.pop_total.astype(float)

    def positions(key: str) -> dict[str, np.ndarray]:
        groups: defaultdict[str, list[int]] = defaultdict(list)
        for i, row in enumerate(rows):
            groups[getattr(row, key)].append(i)
        return {code: np.array(items) for code, items in groups.items()}

    def aggregate(items: np.ndarray) -> Any:
        return aggregate_cells(
            pop[items],
            inputs.share_ge65[items],
            index.ikr[items],
            {name: values[items] for name, values in index.classes.items()},
            high,
        )

    # Census totals come from DZS (ADR 0005); the grid gives the risk and the exposure.
    census = {
        row.jls_code: row
        for row in conn.execute(
            text(
                "SELECT p.jls_code, p.pop_total, p.pop_ge65, j.zupanija_code "
                "FROM pop.jls_2021 p JOIN ref.jls j ON j.code = p.jls_code"
            )
        )
    }
    jls_groups = positions("jls_code")
    codes = [code for code in census if code in jls_groups]
    aggregates = {code: aggregate(jls_groups[code]) for code in codes}
    jls_ikr = np.array(
        [
            np.nan if aggregates[code].ikr_popw is None else aggregates[code].ikr_popw
            for code in codes
        ]
    )
    jls_class = quintile_classes(jls_ikr)
    rank_hr = competition_ranks(jls_ikr)
    rank_zup = np.zeros(len(codes), dtype=np.int32)
    by_county: defaultdict[str, list[int]] = defaultdict(list)
    for i, code in enumerate(codes):
        by_county[census[code].zupanija_code].append(i)
    for members in by_county.values():
        rank_zup[members] = competition_ranks(jls_ikr[members])

    upsert_rows(
        conn,
        "idx.risk_jls",
        (
            "run_id",
            "jls_code",
            "pop",
            "pop65",
            "ikr_popw",
            "ikr_class",
            "exposed",
            "rank_hr",
            "rank_zup",
        ),
        ("run_id", "jls_code"),
        (
            (
                run_id,
                code,
                census[code].pop_total,
                census[code].pop_ge65,
                aggregates[code].ikr_popw,
                _class(jls_class[i]),
                json.dumps(aggregates[code].exposed),
                int(rank_hr[i]) or None,
                int(rank_zup[i]) or None,
            )
            for i, code in enumerate(codes)
        ),
    )

    naselje_groups = positions("naselje_code")
    naselje_codes = list(naselje_groups)
    naselje_aggregates = {code: aggregate(naselje_groups[code]) for code in naselje_codes}
    naselje_ikr = np.array(
        [
            np.nan
            if naselje_aggregates[code].ikr_popw is None
            else naselje_aggregates[code].ikr_popw
            for code in naselje_codes
        ]
    )
    naselje_class = quintile_classes(naselje_ikr)
    upsert_rows(
        conn,
        "idx.risk_naselja",
        ("run_id", "naselje_code", "pop", "ikr_popw", "ikr_class", "exposed"),
        ("run_id", "naselje_code"),
        (
            (
                run_id,
                code,
                int(naselje_aggregates[code].pop),
                naselje_aggregates[code].ikr_popw,
                _class(naselje_class[i]),
                json.dumps(naselje_aggregates[code].exposed),
            )
            for i, code in enumerate(naselje_codes)
        ),
    )

    conn.execute(
        text("UPDATE idx.runs SET status = 'success', finished_at = :now WHERE run_id = :id"),
        {"now": datetime.now(UTC), "id": run_id},
    )
    conn.execute(
        text(
            "DELETE FROM idx.runs WHERE run_id NOT IN "
            "(SELECT run_id FROM idx.runs ORDER BY run_id DESC LIMIT :keep)"
        ),
        {"keep": KEEP_RUNS},
    )
    log.info("index computed", run_id=run_id, cells=len(rows), jls=len(codes))
    return run_id
