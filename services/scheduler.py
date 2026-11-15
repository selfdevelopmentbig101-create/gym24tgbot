"""
Reminder scheduling with APScheduler.

The database (reminder_settings) is the source of truth. On startup every
user's jobs are rebuilt from it, and whenever settings change we call sync().
That's why an in-memory job store is enough: nothing is lost on restart.

Jobs per user (internal user id):
  workout:{id}  on chosen weekdays at workout_time
  nudge:{id}    same weekdays at nudge_time: "missed today's workout?"
  weighin:{id}  daily or weekly at weighin_time
  resched:{id}  one-off reminder after "remind me tomorrow"
  summary:{id}  daily nutrition summary at summary_time (sent only if food was logged)
The job only calls `notify(kind, user_id)`; the Telegram side decides what to send.
"""
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ReminderSettings
from services.reminders import parse_hhmm, parse_tz

logger = logging.getLogger(__name__)

Notify = Callable[[str, int], Awaitable[None]]
JOB_KINDS = ("workout", "nudge", "weighin", "resched", "summary")


class ReminderScheduler:
    def __init__(self, notify: Notify):
        self.notify = notify
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)

    def start(self) -> None:
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def remove_user(self, user_id: int) -> None:
        for kind in JOB_KINDS:
            job = self.scheduler.get_job(f"{kind}:{user_id}")
            if job is not None:
                job.remove()

    def _add(self, kind: str, user_id: int, trigger) -> None:
        self.scheduler.add_job(
            self.notify, trigger, args=[kind, user_id], id=f"{kind}:{user_id}",
            replace_existing=True, coalesce=True, misfire_grace_time=3600,
        )

    def sync(self, user_id: int, settings: ReminderSettings | None) -> None:
        """Make this user's jobs match their settings."""
        self.remove_user(user_id)
        if settings is None:
            return
        tz = parse_tz(settings.timezone)
        days = ",".join(str(d) for d in sorted(settings.workout_days or []))

        if settings.workout_enabled and days:
            at = parse_hhmm(settings.workout_time)
            self._add("workout", user_id, CronTrigger(day_of_week=days, hour=at.hour,
                                                      minute=at.minute, timezone=tz))
            if settings.nudge_enabled:
                at = parse_hhmm(settings.nudge_time)
                self._add("nudge", user_id, CronTrigger(day_of_week=days, hour=at.hour,
                                                        minute=at.minute, timezone=tz))
        if settings.weighin_mode in ("daily", "weekly"):
            at = parse_hhmm(settings.weighin_time)
            weekday = "*" if settings.weighin_mode == "daily" else str(settings.weighin_day)
            self._add("weighin", user_id, CronTrigger(day_of_week=weekday, hour=at.hour,
                                                      minute=at.minute, timezone=tz))
        if settings.summary_enabled:
            at = parse_hhmm(settings.summary_time)
            self._add("summary", user_id, CronTrigger(hour=at.hour, minute=at.minute, timezone=tz))
        when = settings.rescheduled_for
        if when is not None:
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            if when > datetime.now(timezone.utc):
                self._add("resched", user_id, DateTrigger(run_date=when))

    async def load_all(self, session: AsyncSession) -> int:
        count = 0
        for settings in await session.scalars(select(ReminderSettings)):
            try:
                self.sync(settings.user_id, settings)
                count += 1
            except ValueError:
                logger.warning("Skipping reminders with an invalid time zone")
        logger.info("Reminders scheduled for %s users", count)
        return count

    def jobs_for(self, user_id: int) -> dict[str, object]:
        return {kind: job for kind in JOB_KINDS
                if (job := self.scheduler.get_job(f"{kind}:{user_id}")) is not None}


# The running scheduler (set in bot.py). None in tests that don't need it.
_scheduler: ReminderScheduler | None = None


def set_scheduler(scheduler: ReminderScheduler | None) -> None:
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> ReminderScheduler | None:
    return _scheduler


def sync_user(user_id: int, settings: ReminderSettings | None) -> None:
    """Convenience for handlers: sync if a scheduler is running."""
    if _scheduler is not None:
        _scheduler.sync(user_id, settings)
