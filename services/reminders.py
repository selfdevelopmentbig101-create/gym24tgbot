"""
Reminder settings, time zones and "did the user train today?" checks.
The scheduling itself lives in services/scheduler.py.
"""
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BodyWeightLog, ReminderSettings, User, WorkoutSession, utcnow

# UTC offsets (in minutes) offered as buttons, including half-hour zones.
OFFSETS_MINUTES = sorted(
    [h * 60 for h in range(-12, 15)] + [-210, 210, 270, 330, 345, 390, 570]
)

# Default weekdays (0 = Monday) for each number of training days.
DEFAULT_WORKOUT_DAYS = {
    2: [0, 3], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 2, 4, 5], 6: [0, 1, 2, 3, 4, 5],
}
REMINDER_HOURS = list(range(5, 24))  # times offered as buttons


def offset_name(minutes: int) -> str:
    """330 -> 'UTC+05:30'."""
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{mins:02d}"


def parse_tz(name: str) -> tzinfo:
    """'UTC', 'UTC+05:30' or an IANA name like 'Europe/Berlin'. Raises ValueError."""
    name = (name or "").strip()
    if name.upper() == "UTC":
        return timezone.utc
    if name.upper().startswith("UTC") and len(name) == 9 and name[3] in "+-":
        hours, mins = int(name[4:6]), int(name[7:9])
        minutes = hours * 60 + mins
        return timezone(timedelta(minutes=minutes if name[3] == "+" else -minutes))
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"Unknown time zone: {name}") from error


def is_valid_tz(name: str) -> bool:
    try:
        parse_tz(name)
        return True
    except ValueError:
        return False


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def local_now(settings: ReminderSettings | None, now: datetime | None = None) -> datetime:
    tz = parse_tz(settings.timezone) if settings else timezone.utc
    return (now or utcnow()).astimezone(tz)


def local_day_bounds_utc(settings: ReminderSettings | None, day: date) -> tuple[datetime, datetime]:
    """Start and end of a local calendar day, in UTC (for database queries)."""
    tz = parse_tz(settings.timezone) if settings else timezone.utc
    start = datetime.combine(day, time(0, 0), tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


# ---------- Settings ----------

async def get_settings(session: AsyncSession, user: User) -> ReminderSettings | None:
    return await session.get(ReminderSettings, user.id)


async def enable(session: AsyncSession, user: User, tz_name: str) -> ReminderSettings:
    """Turn reminders on with sensible defaults (or just change the time zone)."""
    if not is_valid_tz(tz_name):
        raise ValueError(tz_name)
    settings = await get_settings(session, user)
    if settings is None:
        days = user.profile.training_days if user.profile else 3
        settings = ReminderSettings(
            user_id=user.id, timezone=tz_name, workout_enabled=True,
            workout_days=DEFAULT_WORKOUT_DAYS.get(days, [0, 2, 4]), workout_time="18:00",
            weighin_mode="weekly", weighin_day=0, weighin_time="08:00",
            nudge_enabled=True, nudge_time="21:00", missed_streak=0,
        )
        session.add(settings)
    else:
        settings.timezone = tz_name
    await session.commit()
    return settings


async def disable(session: AsyncSession, user: User) -> None:
    settings = await get_settings(session, user)
    if settings is not None:
        await session.delete(settings)
        await session.commit()


async def trained_on(session: AsyncSession, user: User, settings: ReminderSettings | None,
                     day: date) -> bool:
    """Did the user start a workout on this local day?"""
    start, end = local_day_bounds_utc(settings, day)
    found = await session.scalar(
        select(WorkoutSession.id).where(WorkoutSession.user_id == user.id,
                                        WorkoutSession.started_at >= start,
                                        WorkoutSession.started_at < end)
    )
    return found is not None


async def weighed_on(session: AsyncSession, user: User, settings: ReminderSettings | None,
                     day: date) -> bool:
    start, end = local_day_bounds_utc(settings, day)
    found = await session.scalar(
        select(BodyWeightLog.id).where(BodyWeightLog.user_id == user.id,
                                       BodyWeightLog.logged_at >= start,
                                       BodyWeightLog.logged_at < end)
    )
    return found is not None


async def workout_finished(session: AsyncSession, user: User) -> ReminderSettings | None:
    """A workout was finished: reset the missed streak and any reschedule."""
    settings = await get_settings(session, user)
    if settings is not None:
        settings.missed_streak = 0
        settings.rescheduled_for = None
        await session.commit()
    return settings


async def reschedule(session: AsyncSession, settings: ReminderSettings, days_ahead: int) -> datetime:
    """'Remind me tomorrow': a one-off reminder at the usual workout time, N days from now."""
    local = local_now(settings)
    target = datetime.combine(local.date() + timedelta(days=days_ahead),
                              parse_hhmm(settings.workout_time), tzinfo=local.tzinfo)
    settings.rescheduled_for = target.astimezone(timezone.utc)
    await session.commit()
    return target
