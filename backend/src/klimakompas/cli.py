"""The `kk` command line."""

from typing import Annotated

import structlog
import typer

from klimakompas.core.config import ROOT, get_settings, load_sources
from klimakompas.core.http import HttpClient
from klimakompas.core.logging import configure_logging
from klimakompas.sources.verify import has_p0_failure, render_report, verify_sources

app = typer.Typer(no_args_is_help=True)
sources_app = typer.Typer(no_args_is_help=True)
app.add_typer(sources_app, name="sources")


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
