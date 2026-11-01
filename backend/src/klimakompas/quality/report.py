"""Data quality checks per source, stored in meta.dq_checks (SPEC §15.1)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, text

from klimakompas.core.config import Source, load_sources, load_thresholds


@dataclass(frozen=True)
class QualityCheck:
    source_id: str
    check_id: str
    passed: bool
    value: float | None
    details: dict[str, Any]


def iso_duration(value: str) -> timedelta:
    """The only forms used in sources.yaml: PT6H and P3D."""
    number = int(value.strip("PTHD"))
    return timedelta(hours=number) if value.endswith("H") else timedelta(days=number)


def freshness_check(source: Source, last_success: datetime | None, now: datetime) -> QualityCheck:
    limit = iso_duration(source.stale_after or "P365D")
    if last_success is None:
        return QualityCheck(source.id, "freshness", False, None, {"reason": "never loaded"})
    age = now - last_success
    return QualityCheck(
        source.id,
        "freshness",
        age <= limit,
        round(age.total_seconds() / 3600, 2),
        {"unit": "h", "limit_hours": limit.total_seconds() / 3600},
    )


def portal_check(source: Source, row: Any) -> QualityCheck:
    """Whether the Portal record states a licence and its publisher is active."""
    if row is None:
        return QualityCheck(source.id, "portal_metadata", False, None, {"reason": "no record read"})
    organization = row.organization or ""
    license_present = bool(row.license_title)
    active = "NEAKTIVAN" not in organization
    return QualityCheck(
        source.id,
        "portal_metadata",
        license_present and active,
        None,
        {
            "license_present": license_present,
            "publisher_active": active,
            "publisher": organization,
            "license": row.license_title,
        },
    )


def _range_checks(conn: Connection) -> list[QualityCheck]:
    specs = [
        ("eea_pm25_1km", "pm25_range", "haz.air_cell", "pm25_annual", 0.0, 1000.0),
        ("jrc_efas_flood", "flood_range", "haz.flood_cell", "h_flood", 0.0, 1.0),
        ("ecde", "hot_days_range", "haz.heat_cell", "hot_days", 0.0, 200.0),
        ("ecde", "fwi_days_range", "haz.fire_cell", "fwi_days", 0.0, 365.0),
        ("azo_aq_rest", "aq_range", "live.aq_obs", "value", 0.0, 1000.0),
    ]
    checks = []
    for source_id, check_id, table, column, low, high in specs:
        row = conn.execute(
            text(f"SELECT min({column}), max({column}), count(*) FROM {table}")
        ).one()
        minimum, maximum, count = row
        passed = count > 0 and minimum >= low and maximum <= high
        checks.append(
            QualityCheck(
                source_id,
                check_id,
                bool(passed),
                float(count),
                {"min": minimum, "max": maximum, "allowed": [low, high]},
            )
        )
    return checks


def _completeness_checks(conn: Connection, now: datetime) -> list[QualityCheck]:
    active, recent = conn.execute(
        text(
            """
            SELECT count(*) FILTER (WHERE last_obs_at > :week),
                   count(*) FILTER (WHERE last_obs_at > :hours)
            FROM live.aq_stations
            """
        ),
        {"week": now - timedelta(days=7), "hours": now - timedelta(hours=3)},
    ).one()
    total = conn.execute(text("SELECT count(*) FROM live.aq_stations")).scalar_one()
    share = recent / active if active else 0.0
    stale_share = 1 - (active / total) if total else 0.0
    checks = [
        QualityCheck(
            "azo_aq_rest",
            "stations_reporting_3h",
            share >= 0.5,
            round(share, 3),
            {"recent": recent, "active_7d": active},
        ),
        QualityCheck(
            "azo_aq_rest",
            "stations_silent_7d",
            stale_share <= 0.5,
            round(stale_share, 3),
            {"listed": total, "active_7d": active},
        ),
    ]
    gaps = conn.execute(
        text("SELECT count(*) FROM haz.air_cell WHERE pm25_annual IS NULL")
    ).scalar_one()
    checks.append(QualityCheck("eea_pm25_1km", "cells_without_value", gaps == 0, float(gaps), {}))
    return checks


def _key_checks(conn: Connection) -> list[QualityCheck]:
    controls = load_thresholds()["controls"]
    jls = conn.execute(text("SELECT count(*) FROM ref.jls")).scalar_one()
    without_pop = conn.execute(
        text(
            "SELECT count(*) FROM ref.naselja n "
            "LEFT JOIN pop.naselja_2021 p ON p.naselje_code = n.code "
            "WHERE p.naselje_code IS NULL"
        )
    ).scalar_one()
    return [
        QualityCheck(
            "dgu_au", "jls_keys", jls == controls["jls"], float(jls), {"expected": controls["jls"]}
        ),
        QualityCheck(
            "dzs_naselja_2021",
            "register_settlements_without_census",
            without_pop == 0,
            float(without_pop),
            {"note": "Naselja novija od Popisa 2021. (ADR 0005)"},
        ),
    ]


def run_quality(conn: Connection) -> list[QualityCheck]:
    now = datetime.now(UTC)
    status: dict[str, datetime | None] = dict(
        conn.execute(text("SELECT source_id, last_success_at FROM meta.sources")).tuples().all()
    )
    portal = {
        row.source_id: row
        for row in conn.execute(
            text("SELECT source_id, organization, license_title FROM meta.ckan_metadata")
        )
    }
    checks: list[QualityCheck] = []
    for source in load_sources():
        if source.stale_after:
            checks.append(freshness_check(source, status.get(source.id), now))
        if source.data_gov_hr_id:
            checks.append(portal_check(source, portal.get(source.id)))
    checks += _range_checks(conn) + _completeness_checks(conn, now) + _key_checks(conn)
    for check in checks:
        conn.execute(
            text(
                """
                INSERT INTO meta.dq_checks (source_id, check_id, status, value, details, checked_at)
                VALUES (:source, :check, :status, :value, CAST(:details AS jsonb), :now)
                ON CONFLICT (source_id, check_id) DO UPDATE SET status = EXCLUDED.status,
                    value = EXCLUDED.value, details = EXCLUDED.details,
                    checked_at = EXCLUDED.checked_at
                """
            ),
            {
                "source": check.source_id,
                "check": check.check_id,
                "status": "pass" if check.passed else "fail",
                "value": check.value,
                "details": json.dumps(check.details, ensure_ascii=False, default=str),
                "now": now,
            },
        )
    return checks


def list_checks(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT source_id, check_id, status, value, details, checked_at "
            "FROM meta.dq_checks ORDER BY status, source_id, check_id"
        )
    ).mappings()
    return [dict(row) for row in rows]
