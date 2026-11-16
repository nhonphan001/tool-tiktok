"""Lập lịch quét định kỳ bằng APScheduler."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import scanner
from .config import settings

log = logging.getLogger(__name__)
JOB_ID = "periodic_scan"
_scheduler: BackgroundScheduler | None = None


def start() -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
    reschedule()


def reschedule() -> None:
    if _scheduler is None:
        return
    hours = max(float(settings.scan_interval_hours), 0.25)
    _scheduler.add_job(
        lambda: scanner.run_scan("schedule"),
        "interval",
        hours=hours,
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Scheduled scan every %s hours", hours)


def next_run():
    if _scheduler is None:
        return None
    job = _scheduler.get_job(JOB_ID)
    return job.next_run_time if job else None


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
