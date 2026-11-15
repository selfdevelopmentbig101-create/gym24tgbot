"""
Auto-adjustments (no Telegram code). The bot only *suggests*; nothing changes
until the user taps Accept.

1. Deload: if 2+ exercises have stalled (no estimated-1RM progress over the
   last 3 workouts compared with earlier ones), suggest one lighter week:
   ~60% of the sets at ~90% of the weight. Lets fatigue drop so progress resumes.
2. Calories: if weight gain was too slow (or too fast) for the goal two weeks
   in a row, suggest +150 kcal (or -150 kcal) a day.

Safety: calorie changes are small steps within -300...+450 kcal in total;
the calculator's floor (never below BMR) still applies. Each suggestion has a
cooldown so users aren't nagged.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, SetLog, User, utcnow
from services import body, records, reminders
from services.body import aware
from services.nutrition import targets_for_profile
from services.progression import round_to_step

KCAL_STEP = 150
KCAL_ADJUST_RANGE = (-300, 450)
KCAL_COOLDOWN = timedelta(days=14)
DELOAD_COOLDOWN = timedelta(days=21)
DELOAD_DAYS = 7
DELOAD_SET_FACTOR = 0.6
DELOAD_WEIGHT_FACTOR = 0.9
STALL_WINDOW_DAYS = 42
STALL_MIN_SESSIONS = 4
MIN_STALLED = 2


@dataclass(frozen=True)
class CalorieSuggestion:
    delta: int          # +150 or -150
    trend: float        # kg/week, most recent
    new_calories: int


# ---------- Deload ----------

def deload_active(profile, today: date) -> bool:
    return profile.deload_until is not None and today < profile.deload_until


def deload_sets(sets: int) -> int:
    return max(2, round(sets * DELOAD_SET_FACTOR))


def deload_weight(weight: float) -> float:
    return round_to_step(weight * DELOAD_WEIGHT_FACTOR)


def _recent(dt: datetime | None, window: timedelta) -> bool:
    return dt is not None and utcnow() - aware(dt) < window


async def stalled_exercises(session: AsyncSession, user: User) -> list[Exercise]:
    since = utcnow() - timedelta(days=STALL_WINDOW_DAYS)
    ids = set(await session.scalars(
        select(SetLog.exercise_id).where(SetLog.user_id == user.id, SetLog.weight_kg > 0,
                                         SetLog.created_at >= since)
    ))
    stalled = []
    for exercise_id in ids:
        history = await records.e1rm_history(session, user, exercise_id, since)
        if len(history) < STALL_MIN_SESSIONS:
            continue
        values = [value for _, value in history]
        last_seen = history[-1][0]
        if utcnow() - aware(last_seen) > timedelta(days=14):
            continue  # not doing this exercise anymore
        if max(values[-3:]) <= max(values[:-3]) + 0.01:
            stalled.append(await session.get(Exercise, exercise_id))
    return sorted(stalled, key=lambda e: e.name)


async def deload_suggestion(session: AsyncSession, user: User) -> list[Exercise] | None:
    """Stalled exercises if a deload should be offered now, else None."""
    profile = user.profile
    today = reminders.local_now(await reminders.get_settings(session, user)).date()
    if deload_active(profile, today) or _recent(profile.deload_offered_at, DELOAD_COOLDOWN):
        return None
    if profile.deload_until and today - profile.deload_until < timedelta(days=28):
        return None  # had one recently
    stalled = await stalled_exercises(session, user)
    return stalled if len(stalled) >= MIN_STALLED else None


async def start_deload(session: AsyncSession, user: User) -> date:
    today = reminders.local_now(await reminders.get_settings(session, user)).date()
    user.profile.deload_until = today + timedelta(days=DELOAD_DAYS)
    user.profile.deload_offered_at = utcnow()
    await session.commit()
    return user.profile.deload_until


async def dismiss_deload(session: AsyncSession, user: User) -> None:
    user.profile.deload_offered_at = utcnow()
    await session.commit()


# ---------- Calories ----------

async def calorie_suggestion(session: AsyncSession, user: User,
                             now: datetime | None = None) -> CalorieSuggestion | None:
    profile = user.profile
    if _recent(profile.kcal_offered_at, KCAL_COOLDOWN):
        return None
    now = now or utcnow()
    trend_now = await body.weekly_trend(session, user, now)
    trend_before = await body.weekly_trend(session, user, now - timedelta(days=7))
    if trend_now is None or trend_before is None:
        return None
    target = targets_for_profile(profile).weekly_gain_kg
    verdicts = {body.classify_trend(trend_now, target), body.classify_trend(trend_before, target)}
    if verdicts == {"slow"}:
        delta = KCAL_STEP
    elif verdicts == {"fast"}:
        delta = -KCAL_STEP
    else:
        return None
    adjust = (profile.calorie_adjust or 0) + delta
    if not KCAL_ADJUST_RANGE[0] <= adjust <= KCAL_ADJUST_RANGE[1]:
        return None
    current = targets_for_profile(profile).calories
    return CalorieSuggestion(delta, trend_now, current + delta)


async def apply_calories(session: AsyncSession, user: User, delta: int) -> int:
    """Accept a calorie change. Returns the new daily target."""
    if delta not in (KCAL_STEP, -KCAL_STEP):
        raise ValueError(delta)
    adjust = (user.profile.calorie_adjust or 0) + delta
    low, high = KCAL_ADJUST_RANGE
    user.profile.calorie_adjust = max(low, min(high, adjust))
    user.profile.kcal_offered_at = utcnow()
    await session.commit()
    return targets_for_profile(user.profile).calories


async def dismiss_calories(session: AsyncSession, user: User) -> None:
    user.profile.kcal_offered_at = utcnow()
    await session.commit()
