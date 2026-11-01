"""The `kk` command line."""

from typing import Annotated

import structlog
import typer

from klimakompas.core.config import ROOT, Source, get_settings, load_sources
from klimakompas.core.db import get_engine
from klimakompas.core.http import HttpClient
from klimakompas.core.logging import configure_logging
from klimakompas.pipeline.tiles import refresh_tiles
from klimakompas.sources.base import Connector, RunContext, run_connector
from klimakompas.sources.dgu_ad import DguAdConnector
from klimakompas.sources.dgu_au import DguAuConnector
from klimakompas.sources.dzs_naselja import DzsNaseljaConnector
from klimakompas.sources.estat_census import EstatCensusConnector
from klimakompas.sources.verify import has_p0_failure, render_report, verify_sources

app = typer.Typer(no_args_is_help=True)
sources_app = typer.Typer(no_args_is_help=True)
app.add_typer(sources_app, name="sources")
etl_app = typer.Typer(no_args_is_help=True)
app.add_typer(etl_app, name="etl")
tiles_app = typer.Typer(no_args_is_help=True)
app.add_typer(tiles_app, name="tiles")

# Order matters: DZS matches against the register, the census grid needs the grid and DZS totals.
CONNECTORS: dict[str, Connector] = {
    connector.source_id: connector
    for connector in (
        DguAuConnector(),
        DzsNaseljaConnector(),
        EstatCensusConnector(),
        DguAdConnector(),
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
    engine = get_engine()
    with HttpClient(settings.kk_user_agent) as client:
        for source_id in source_ids:
            ctx = RunContext(source=sources[source_id], client=client, data_dir=ROOT / "data")
            result = run_connector(CONNECTORS[source_id], ctx, engine)
            log.info("etl finished", source=source_id, rows=result.rows)
    with engine.begin() as conn:
        refresh_tiles(conn)
    log.info("tile views refreshed")


@etl_app.command("run")
def etl_run(source: str) -> None:
    """Fetch and load one source."""
    if source not in CONNECTORS:
        raise typer.BadParameter(f"no connector for: {source}")
    _run([source])


@etl_app.command("run-all")
def etl_run_all() -> None:
    """Fetch and load every implemented source in dependency order."""
    _run(list(CONNECTORS))


@tiles_app.command("refresh")
def tiles_refresh() -> None:
    """Refresh the materialized views served by Martin."""
    with get_engine().begin() as conn:
        refresh_tiles(conn)
