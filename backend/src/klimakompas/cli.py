"""The `kk` command line."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
import typer

from klimakompas.core.config import ROOT, Source, get_settings, load_sources
from klimakompas.core.db import get_engine
from klimakompas.core.http import HttpClient
from klimakompas.core.logging import configure_logging
from klimakompas.live.connectors import (
    AzoConnector,
    BioportalConnector,
    CapConnector,
    CkanConnector,
    FireIndexConnector,
    HeatwaveConnector,
)
from klimakompas.pipeline.compute_index import compute_index
from klimakompas.pipeline.sensitivity import run_sensitivity
from klimakompas.pipeline.tiles import refresh_tiles
from klimakompas.quality.exports import write_catalog, write_exports
from klimakompas.quality.report import run_quality
from klimakompas.sources.base import Connector, RunContext, run_connector
from klimakompas.sources.dgu_ad import DguAdConnector
from klimakompas.sources.dgu_au import DguAuConnector
from klimakompas.sources.dzs_naselja import DzsNaseljaConnector
from klimakompas.sources.estat_census import EstatCensusConnector
from klimakompas.sources.hazards import (
    AirConnector,
    BurntConnector,
    EcdeConnector,
    FloodConnector,
    LandsatConnector,
    WorldCoverConnector,
)
from klimakompas.sources.verify import has_p0_failure, render_report, verify_sources
from klimakompas.worker.scheduler import run_worker

app = typer.Typer(no_args_is_help=True)
sources_app = typer.Typer(no_args_is_help=True)
app.add_typer(sources_app, name="sources")
etl_app = typer.Typer(no_args_is_help=True)
app.add_typer(etl_app, name="etl")
tiles_app = typer.Typer(no_args_is_help=True)
app.add_typer(tiles_app, name="tiles")
index_app = typer.Typer(no_args_is_help=True)
app.add_typer(index_app, name="index")
ml_app = typer.Typer(no_args_is_help=True)
app.add_typer(ml_app, name="ml")
quality_app = typer.Typer(no_args_is_help=True)
app.add_typer(quality_app, name="quality")
export_app = typer.Typer(no_args_is_help=True)
app.add_typer(export_app, name="export")

# Order matters: DZS matches against the register, the census grid needs the grid and DZS totals.
CONNECTORS: dict[str, Connector] = {
    connector.source_id: connector
    for connector in (
        DguAuConnector(),
        DzsNaseljaConnector(),
        EstatCensusConnector(),
        DguAdConnector(),
        FloodConnector(),
        AirConnector(),
        WorldCoverConnector(),
        LandsatConnector(),
        BurntConnector(),
        EcdeConnector(),
    )
}
# Refreshed by the worker on their own schedules.
LIVE_CONNECTORS: dict[str, Connector] = {
    connector.source_id: connector
    for connector in (
        CapConnector(),
        HeatwaveConnector(),
        FireIndexConnector(),
        AzoConnector(),
        CkanConnector(),
        BioportalConnector(),
    )
}


@sources_app.command("verify")
def sources_verify(
    source: Annotated[str | None, typer.Option(help="Check only this source id.")] = None,
    save_fixtures: Annotated[
        bool, typer.Option(help="Write responses marked as fixtures to backend/tests/fixtures.")
    ] = False,
) -> None:
    """Check every source in config/sources.yaml and write docs/izvori-provjera.md."""
    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger()

    sources = load_sources()
    if source:
        sources = [entry for entry in sources if entry.id == source]
        if not sources:
            raise typer.BadParameter(f"unknown source id: {source}")

    with HttpClient(settings.kk_user_agent) as client:
        results = verify_sources(
            sources,
            client,
            data_dir=ROOT / "data",
            fixtures_dir=ROOT / "backend" / "tests" / "fixtures" if save_fixtures else None,
        )

    if source:
        log.info("single source checked, report not rewritten", source=source)
    else:
        report = ROOT / "docs" / "izvori-provjera.md"
        report.write_text(render_report(results), encoding="utf-8")
        log.info("report written", path=str(report))

    if has_p0_failure(results):
        log.error("at least one P0 source failed")
        raise typer.Exit(code=1)


def _run(source_ids: list[str]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger()
    sources: dict[str, Source] = {entry.id: entry for entry in load_sources()}
    connectors = {**CONNECTORS, **LIVE_CONNECTORS}
    engine = get_engine()
    with HttpClient(settings.kk_user_agent) as client:
        for source_id in source_ids:
            ctx = RunContext(source=sources[source_id], client=client, data_dir=ROOT / "data")
            result = run_connector(connectors[source_id], ctx, engine)
            log.info("etl finished", source=source_id, rows=result.rows)


@etl_app.command("run")
def etl_run(source: str) -> None:
    """Fetch and load one source. Static layers need `kk tiles refresh` afterwards."""
    if source not in CONNECTORS and source not in LIVE_CONNECTORS:
        raise typer.BadParameter(f"no connector for: {source}")
    _run([source])


@etl_app.command("run-all")
def etl_run_all(
    static: Annotated[bool, typer.Option(help="Run only the batch sources.")] = False,
    live: Annotated[bool, typer.Option(help="Run only the live sources.")] = False,
) -> None:
    """Fetch and load every implemented source in dependency order."""
    run_static = static or not live
    run_live = live or not static
    _run([*(CONNECTORS if run_static else []), *(LIVE_CONNECTORS if run_live else [])])
    if run_static:
        with get_engine().begin() as conn:
            refresh_tiles(conn)


@tiles_app.command("refresh")
def tiles_refresh() -> None:
    """Refresh the materialized views served by Martin."""
    with get_engine().begin() as conn:
        refresh_tiles(conn)


@app.command("worker")
def worker() -> None:
    """Run the live sources on their schedules."""
    configure_logging(get_settings().log_level)
    run_worker(LIVE_CONNECTORS)


@index_app.command("compute")
def index_compute() -> None:
    """Compute the Climate Risk Index from the hazard tables and refresh the tile views."""
    settings = get_settings()
    configure_logging(settings.log_level)
    with get_engine().begin() as conn:
        compute_index(conn)
        refresh_tiles(conn)


@ml_app.command("backfill")
def ml_backfill() -> None:
    """Fetch two years of hourly PM2.5 for stations that currently report it."""
    from klimakompas.ml.nowcast import backfill_station, stations_with_pm25

    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger()
    engine = get_engine()
    today = datetime.now(UTC).date()
    with engine.connect() as conn:
        stations = stations_with_pm25(conn)
    with HttpClient(settings.kk_user_agent) as client:
        for station in stations:
            rows = backfill_station(client, engine, station.station_id, today)
            log.info("backfilled", station=station.name, rows=rows)


@ml_app.command("train")
def ml_train() -> None:
    """Train the nowcast, validate it on rolling windows and write docs/ml-rezultati.json."""
    from klimakompas.ml.nowcast import train

    settings = get_settings()
    configure_logging(settings.log_level)
    with HttpClient(settings.kk_user_agent) as client:
        metrics = train(get_engine(), client)
    structlog.get_logger().info("trained", overall=metrics["overall"])


@ml_app.command("predict")
def ml_predict() -> None:
    """Write the next forecast for stations with fresh values."""
    from klimakompas.ml.nowcast import predict

    settings = get_settings()
    configure_logging(settings.log_level)
    with HttpClient(settings.kk_user_agent) as client:
        rows = predict(get_engine(), client)
    structlog.get_logger().info("forecast written", rows=rows)


@index_app.command("sensitivity")
def index_sensitivity() -> None:
    """Rank stability under random hazard weights; writes docs/osjetljivost-rezultati.json."""
    configure_logging(get_settings().log_level)
    with get_engine().connect() as conn:
        result = run_sensitivity(conn)
    structlog.get_logger().info("sensitivity", median=result["median_spearman"])


@quality_app.command("report")
def quality_report() -> None:
    """Run the data quality checks and store them in meta.dq_checks."""
    configure_logging(get_settings().log_level)
    with get_engine().begin() as conn:
        checks = run_quality(conn)
    structlog.get_logger().info(
        "quality", total=len(checks), failed=[c.check_id for c in checks if not c.passed]
    )


@export_app.command("all")
def export_all() -> None:
    """Write the derived datasets and the DCAT-AP catalogue to data/export."""
    settings = get_settings()
    configure_logging(settings.log_level)
    counts = write_exports(get_engine())
    write_catalog(settings.public_base_url)
    structlog.get_logger().info("exported", **counts)
