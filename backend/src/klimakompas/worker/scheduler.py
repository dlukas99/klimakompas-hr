"""`kk worker`: runs the live sources on the cron schedules from config/sources.yaml (SPEC §8.2)."""

from collections.abc import Callable

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from klimakompas.core.config import ROOT, Source, get_settings, load_sources
from klimakompas.core.db import get_engine
from klimakompas.core.http import HttpClient
from klimakompas.sources.base import Connector, RunContext, run_connector

log = structlog.get_logger()

TIME_ZONE = "Europe/Zagreb"
MISFIRE_GRACE_S = 600


def _job(connector: Connector, source: Source) -> Callable[[], None]:
    def run() -> None:
        try:
            with HttpClient(get_settings().kk_user_agent) as client:
                ctx = RunContext(source=source, client=client, data_dir=ROOT / "data")
                result = run_connector(connector, ctx, get_engine())
            log.info("live source refreshed", source=source.id, rows=result.rows)
        except Exception as error:
            # A failed source keeps its last good data; the worker itself must keep running.
            log.warning("live source failed", source=source.id, error=type(error).__name__)

    return run


def run_worker(connectors: dict[str, Connector]) -> None:
    scheduler = BlockingScheduler(timezone=TIME_ZONE)
    for source in load_sources():
        if source.id in connectors and source.schedule:
            scheduler.add_job(
                _job(connectors[source.id], source),
                CronTrigger.from_crontab(source.schedule, timezone=TIME_ZONE),
                id=source.id,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=MISFIRE_GRACE_S,
            )
            log.info("scheduled", source=source.id, cron=source.schedule)
    scheduler.start()
