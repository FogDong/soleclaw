from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, TYPE_CHECKING
from zoneinfo import ZoneInfo

from croniter import croniter

from .store import CronStore
from .types import CronJob
from ..bus.events import OutboundMessage

if TYPE_CHECKING:
    from ..core.bridge import SoleclawBridge
    from ..bus.queue import MessageBus

log = logging.getLogger(__name__)

CRON_PREAMBLE = "[CRON] Your response will be sent directly to the user. Only output the content meant for them — no status updates, no tool call summaries, no extra commentary.\n\n"
MAX_TIMER_DELAY_S = 60
STUCK_RUN_THRESHOLD_S = 7200
BACKOFF_SCHEDULE = [30, 60, 300, 900, 3600]


def _tz_now(tz_name: str = "UTC") -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now(timezone.utc)


def compute_next_run(job: CronJob, after: datetime | None = None) -> str:
    now = after or _tz_now(job.schedule_tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if job.schedule_kind == "at":
        t = datetime.fromisoformat(job.schedule_value)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.isoformat() if t > now else ""

    if job.schedule_kind == "every":
        interval = int(job.schedule_value)
        if job.last_run_at:
            last = datetime.fromisoformat(job.last_run_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            return (last + timedelta(seconds=interval)).isoformat()
        return now.isoformat()

    if job.schedule_kind == "cron":
        try:
            tz = ZoneInfo(job.schedule_tz) if job.schedule_tz != "UTC" else timezone.utc
        except Exception:
            tz = timezone.utc
        local_now = now.astimezone(tz)
        cron = croniter(job.schedule_value, local_now)
        next_dt = cron.get_next(datetime)
        return next_dt.astimezone(timezone.utc).isoformat()

    return ""


def is_due(job: CronJob) -> bool:
    if not job.enabled or not job.next_run_at or job.running_at:
        return False
    now = datetime.now(timezone.utc)
    next_run = datetime.fromisoformat(job.next_run_at)
    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=timezone.utc)
    return next_run <= now


def _backoff_delay(consecutive_errors: int) -> int:
    idx = min(consecutive_errors - 1, len(BACKOFF_SCHEDULE) - 1)
    return BACKOFF_SCHEDULE[max(idx, 0)]


class CronService:
    def __init__(self, store: CronStore, bridge: SoleclawBridge, bus: MessageBus):
        self.store = store
        self.bridge = bridge
        self.bus = bus

    async def run(self) -> None:
        log.info("CronService started (dynamic timer, max_delay=%ds)", MAX_TIMER_DELAY_S)
        self._startup_recovery()
        self._recompute_all()

        while True:
            delay = self._compute_delay()
            log.debug("cron sleep %.1fs", delay)
            await asyncio.sleep(delay)
            try:
                await self._tick()
            except Exception:
                log.exception("CronService tick error")

    def _startup_recovery(self) -> None:
        jobs = self.store.load()
        changed = False
        now = datetime.now(timezone.utc)
        for job in jobs:
            if job.running_at:
                running_dt = datetime.fromisoformat(job.running_at)
                if running_dt.tzinfo is None:
                    running_dt = running_dt.replace(tzinfo=timezone.utc)
                elapsed = (now - running_dt).total_seconds()
                log.warning("cron startup: job %s was running for %.0fs, clearing", job.id, elapsed)
                job.running_at = ""
                job.last_run_status = "error"
                job.last_error = "interrupted (service restart)"
                job.consecutive_errors += 1
                changed = True
        if changed:
            self.store.save(jobs)

    def _recompute_all(self) -> None:
        jobs = self.store.load()
        changed = False
        for job in jobs:
            if job.enabled and not job.next_run_at:
                nxt = compute_next_run(job)
                if nxt:
                    job.next_run_at = nxt
                    changed = True
                else:
                    job.schedule_error_count += 1
                    if job.schedule_error_count >= CronJob.MAX_SCHEDULE_ERRORS:
                        log.warning("cron auto-disable: job %s after %d schedule errors", job.id, job.schedule_error_count)
                        job.enabled = False
                    changed = True
        if changed:
            self.store.save(jobs)

    def _compute_delay(self) -> float:
        jobs = self.store.load()
        now = datetime.now(timezone.utc)
        min_delay = MAX_TIMER_DELAY_S

        for job in jobs:
            if not job.enabled or not job.next_run_at or job.running_at:
                continue
            try:
                next_run = datetime.fromisoformat(job.next_run_at)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                delta = (next_run - now).total_seconds()
                min_delay = min(min_delay, max(delta, 0.5))
            except Exception:
                continue

        return min(min_delay, MAX_TIMER_DELAY_S)

    async def _tick(self) -> None:
        jobs = self.store.load()
        now = datetime.now(timezone.utc)

        for job in jobs:
            if job.running_at:
                running_dt = datetime.fromisoformat(job.running_at)
                if running_dt.tzinfo is None:
                    running_dt = running_dt.replace(tzinfo=timezone.utc)
                if (now - running_dt).total_seconds() > STUCK_RUN_THRESHOLD_S:
                    log.warning("cron stuck: job %s running since %s, clearing", job.id, job.running_at)
                    job.running_at = ""
                    job.last_run_status = "error"
                    job.last_error = f"stuck (>{STUCK_RUN_THRESHOLD_S}s)"
                    job.consecutive_errors += 1
                    self.store.save(jobs)
                    jobs = self.store.load()

        for job in jobs:
            if is_due(job):
                await self._execute(job)

    async def _execute(self, job: CronJob) -> None:
        log.info("cron execute: id=%s name=%s", job.id, job.name)
        now = datetime.now(timezone.utc)

        self.store.update(job.id, running_at=now.isoformat())

        t0 = time.monotonic()
        status = "ok"
        error = ""
        result = None

        try:
            if job.message_kind == "static":
                result = job.message
            else:
                result = await self.bridge.oneshot(CRON_PREAMBLE + job.message)
        except Exception as exc:
            log.exception("cron job %s failed", job.id)
            status = "error"
            error = str(exc)[:500]

        duration_ms = int((time.monotonic() - t0) * 1000)
        end = datetime.now(timezone.utc)

        updates: dict[str, Any] = {
            "running_at": "",
            "last_run_at": end.isoformat(),
            "last_run_status": status,
            "last_error": error,
            "last_duration_ms": duration_ms,
        }

        if status == "ok":
            updates["consecutive_errors"] = 0
        else:
            updates["consecutive_errors"] = job.consecutive_errors + 1

        if job.delete_after_run:
            self.store.remove(job.id)
            self.store.log_run(job.id, status, duration_ms, error)
            if result and job.channel and job.chat_id:
                await self._deliver(job, result)
            return

        if job.schedule_kind == "at":
            updates["enabled"] = False
            updates["next_run_at"] = ""
        else:
            next_run = compute_next_run(job, after=end)
            if status == "error" and updates["consecutive_errors"] > 0:
                backoff = _backoff_delay(updates["consecutive_errors"])
                backoff_time = (end + timedelta(seconds=backoff)).isoformat()
                if next_run and datetime.fromisoformat(next_run) < datetime.fromisoformat(backoff_time):
                    next_run = backoff_time
                    log.info("cron backoff: job %s delayed %ds (errors=%d)", job.id, backoff, updates["consecutive_errors"])
            updates["next_run_at"] = next_run

        self.store.update(job.id, **updates)
        self.store.log_run(job.id, status, duration_ms, error)

        if result and job.channel and job.chat_id:
            await self._deliver(job, result)

    async def _deliver(self, job: CronJob, content: str) -> None:
        log.info("cron deliver: id=%s channel=%s chat=%s thread=%s", job.id, job.channel, job.chat_id, job.thread_id)
        try:
            await self.bus.publish_outbound(OutboundMessage(
                channel=job.channel,
                chat_id=job.chat_id,
                thread_id=job.thread_id,
                content=content,
            ))
        except Exception:
            log.exception("cron delivery failed: job %s", job.id)
