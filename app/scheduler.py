"""Lập lịch quét: giờ cố định theo múi giờ kênh (mặc định 05:00, 11:00, 17:00, 23:00) hoặc theo chu kỳ."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import scanner
from .config import settings

log = logging.getLogger(__name__)
JOB_ID = "periodic_scan"
_scheduler: BackgroundScheduler | None = None


def parse_times(text: str) -> list[tuple[int, int]]:
    out = []
    for part in (text or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        hh, _, mm = part.partition(":")
        try:
            h, m = int(hh), int(mm or 0)
        except ValueError:
            continue
        if 0 <= h <= 23 and 0 <= m <= 59 and (h, m) not in out:
            out.append((h, m))
    return sorted(out)


def build_trigger():
    times = parse_times(settings.scan_times)
    if times:
        return OrTrigger([CronTrigger(hour=h, minute=m, timezone=settings.timezone) for h, m in times]), \
            "giờ cố định " + ", ".join(f"{h:02d}:{m:02d}" for h, m in times)
    hours = max(float(settings.scan_interval_hours), 0.25)
    return IntervalTrigger(hours=hours), f"mỗi {hours:g} giờ"


def describe() -> str:
    return build_trigger()[1]


def start() -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.start()
    reschedule()


def reschedule() -> None:
    if _scheduler is None:
        return
    trigger, label = build_trigger()
    _scheduler.add_job(lambda: scanner.run_scan("schedule"), trigger, id=JOB_ID, replace_existing=True,
                       max_instances=1, coalesce=True, misfire_grace_time=1800)
    log.info("Scheduled scan: %s", label)
    from . import gemini_requests

    def _mail():
        try:
            done = gemini_requests.check_replies()
            if done:
                log.info("Gemini replied: %s", [d["code"] for d in done])
        except Exception:  # noqa: BLE001
            log.exception("check_replies")
        try:
            from . import clips

            for m in clips.sync_all():
                log.info(m)
        except Exception:  # noqa: BLE001
            log.exception("clips.sync_all")

    _scheduler.add_job(_mail, IntervalTrigger(minutes=10), id="mailbox_check", replace_existing=True,
                       max_instances=1, coalesce=True)


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
