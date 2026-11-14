"""
Streaks and achievements (no Telegram code).

- Weekly streak: weeks in a row (Monday to Sunday, in the user's time zone) with at
  least as many finished workouts as the plan's training days. Rest days never
  break it. The current week counts once its goal is met; until then the
  streak is still alive from previous weeks.
- Protein streak: days in a row hitting the protein target (today counts once hit).
- Achievements are unlocked from these stats and kept forever.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Achievement, BodyWeightLog, MealLog, SetLog, User, WorkoutSession
from services import reminders
from services.body import aware
from services.nutrition import targets_for_profile


@dataclass(frozen=True)
class AchievementDef:
    code: str
    emoji: str
    stat: str        # key in Stats
    threshold: float


# Order = display order. Names and descriptions are in utils/texts.py (ach_<code>).
ACHIEVEMENTS: tuple[AchievementDef, ...] = (
    AchievementDef("first_workout", "🎉", "workouts", 1),
    AchievementDef("workouts_10", "💪", "workouts", 10),
    AchievementDef("workouts_25", "🏋️", "workouts", 25),
    AchievementDef("workouts_50", "🦾", "workouts", 50),
    AchievementDef("workouts_100", "👑", "workouts", 100),
    AchievementDef("streak_2", "🔥", "week_streak", 2),
    AchievementDef("streak_4", "🔥", "week_streak", 4),
    AchievementDef("streak_8", "🔥", "week_streak", 8),
    AchievementDef("streak_12", "☄️", "week_streak", 12),
    AchievementDef("first_pr", "🏆", "prs", 1),
    AchievementDef("prs_10", "🥇", "prs", 10),
    AchievementDef("prs_25", "💎", "prs", 25),
    AchievementDef("volume_10t", "🧱", "volume_t", 10),
    AchievementDef("volume_100t", "🏗", "volume_t", 100),
    AchievementDef("protein_3", "🥩", "protein_streak", 3),
    AchievementDef("protein_7", "🍗", "protein_streak", 7),
    AchievementDef("protein_30", "🥇", "protein_streak", 30),
    AchievementDef("weighins_10", "⚖️", "weighins", 10),
)
BY_CODE = {a.code: a for a in ACHIEVEMENTS}


@dataclass(frozen=True)
class Stats:
    workouts: int
    week_streak: int
    week_done: int      # finished workouts this week
    week_goal: int
    prs: int
    volume_t: float     # total kg lifted / 1000
    protein_streak: int
    weighins: int

    def value(self, stat: str) -> float:
        return getattr(self, stat)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_streak(workout_days: list[date], today: date, goal: int) -> tuple[int, int]:
    """(streak in weeks, workouts done this week)."""
    per_week: dict[date, int] = {}
    for day in workout_days:
        per_week[week_start(day)] = per_week.get(week_start(day), 0) + 1
    current = week_start(today)
    done = per_week.get(current, 0)
    streak = 1 if done >= goal else 0
    week = current - timedelta(days=7)
    while per_week.get(week, 0) >= goal:
        streak += 1
        week -= timedelta(days=7)
    return streak, done


def daily_streak(protein_by_day: dict[date, float], today: date, target: float) -> int:
    streak = 1 if protein_by_day.get(today, 0) >= target else 0
    day = today - timedelta(days=1)
    while protein_by_day.get(day, 0) >= target:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def compute_stats(session: AsyncSession, user: User) -> Stats:
    settings = await reminders.get_settings(session, user)
    today = reminders.local_now(settings).date()
    goal = max(1, user.profile.training_days)

    finished = list(await session.scalars(
        select(WorkoutSession.finished_at)
        .where(WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_not(None))
    ))
    days = [reminders.local_now(settings, aware(dt)).date() for dt in finished]
    week_streak, week_done = weekly_streak(days, today, goal)

    prs = await session.scalar(
        select(func.count()).select_from(SetLog).where(SetLog.user_id == user.id, SetLog.pr.is_(True))
    ) or 0
    volume = await session.scalar(
        select(func.coalesce(func.sum(SetLog.weight_kg * SetLog.reps), 0))
        .where(SetLog.user_id == user.id)
    ) or 0
    weighins = await session.scalar(
        select(func.count()).select_from(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
    ) or 0

    rows = await session.execute(
        select(MealLog.day, func.sum(MealLog.protein_g))
        .where(MealLog.user_id == user.id, MealLog.day >= today - timedelta(days=400))
        .group_by(MealLog.day)
    )
    protein_by_day = {day: total for day, total in rows}
    protein_streak = daily_streak(protein_by_day, today, targets_for_profile(user.profile).protein_g)

    return Stats(len(days), week_streak, week_done, goal, int(prs), round(volume / 1000, 1),
                 protein_streak, int(weighins))


async def unlocked(session: AsyncSession, user: User) -> dict[str, Achievement]:
    rows = await session.scalars(select(Achievement).where(Achievement.user_id == user.id))
    return {row.code: row for row in rows}


async def check_new(session: AsyncSession, user: User) -> list[AchievementDef]:
    """Unlock everything the user has earned. Returns only the new ones."""
    if user.profile is None:
        return []
    stats = await compute_stats(session, user)
    have = await unlocked(session, user)
    new = [a for a in ACHIEVEMENTS if a.code not in have and stats.value(a.stat) >= a.threshold]
    for achievement in new:
        session.add(Achievement(user_id=user.id, code=achievement.code))
    if new:
        await session.commit()
    return new
