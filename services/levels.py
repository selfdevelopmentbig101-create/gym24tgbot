"""
Levels, XP, character energy and mood (Stage 6). Rules: services/xp_config.py.

Everything is calculated from data that already exists (workouts, sets, PRs), so
there is no XP table to keep in sync, and /deleteme removes it all automatically.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, User, WorkoutSession
from services import achievements, energy, reminders, workouts
from services import xp_config as cfg
from services.body import aware
from services.exercises import load_catalog


def level_index(xp: int) -> int:
    """The highest level whose XP threshold is reached."""
    index = 0
    for i, (_key, needed) in enumerate(cfg.LEVELS):
        if xp >= needed:
            index = i
    return index


def goal_weeks(days: list[date], goal: int, today: date) -> int:
    """Weeks (Mon-Sun) with at least `goal` finished workouts. The current week counts once met."""
    per_week: dict[date, int] = {}
    for day in days:
        start = day - timedelta(days=day.weekday())
        per_week[start] = per_week.get(start, 0) + 1
    return sum(1 for count in per_week.values() if count >= max(1, goal))


def earned_xp(workout_count: int, prs: int, weeks: int) -> int:
    return workout_count * cfg.XP_PER_WORKOUT + prs * cfg.XP_PER_PR + weeks * cfg.XP_PER_GOAL_WEEK


@dataclass(frozen=True)
class Level:
    index: int
    key: str
    xp: int
    level_xp: int            # XP where this level starts
    next_key: str | None
    next_xp: int | None      # XP where the next level starts (None at the top)

    @property
    def to_next(self) -> int:
        return 0 if self.next_xp is None else max(0, self.next_xp - self.xp)

    @property
    def progress(self) -> int:
        """0-100 within the current level."""
        if self.next_xp is None:
            return 100
        span = self.next_xp - self.level_xp
        return min(100, max(0, round(100 * (self.xp - self.level_xp) / span)))

    def as_dict(self) -> dict:
        return {"index": self.index, "key": self.key, "xp": self.xp, "level_xp": self.level_xp,
                "next_key": self.next_key, "next_xp": self.next_xp, "to_next": self.to_next,
                "progress": self.progress, "max_index": len(cfg.LEVELS) - 1}


def make_level(xp: int) -> Level:
    index = level_index(xp)
    key, level_xp = cfg.LEVELS[index]
    nxt = cfg.LEVELS[index + 1] if index + 1 < len(cfg.LEVELS) else None
    return Level(index, key, xp, level_xp, nxt[0] if nxt else None, nxt[1] if nxt else None)


def _session_energy_left(ws: WorkoutSession, catalog: dict[str, Exercise]) -> int:
    """Energy left after the working sets done in a workout (warm-ups are free)."""
    done = []
    for item in ws.items:
        ex = catalog.get(item["exercise_id"])
        if ex is None:
            continue
        block = energy.SetBlock(ex.muscle_group, tuple(ex.secondary_muscles or ()), ex.movement_type,
                                item["sets"], item["timed"])
        done.append((block, len(workouts.sets_for(ws, ex.id))))
    return energy.energy_left(done)


def recovered(left: int, hours: float) -> int:
    """Energy comes back linearly to 100 within RECOVERY_HOURS."""
    share = min(1.0, max(0.0, hours / cfg.RECOVERY_HOURS))
    return round(left + (100 - left) * share)


def mood_for(energy_now: int, hours_since_finish: float | None, had_pr: bool, in_workout: bool) -> str:
    """celebrating | tired | rested (the character's face and pose)."""
    if not in_workout and hours_since_finish is not None:
        window = cfg.CELEBRATE_PR_HOURS if had_pr else cfg.CELEBRATE_HOURS
        if hours_since_finish <= window:
            return "celebrating"
    if energy_now < cfg.TIRED_BELOW:
        return "tired"
    return "rested"


async def level_view(session: AsyncSession, user: User) -> dict:
    """Level, XP, streak, energy and mood for the character (Home and Profile)."""
    stats = await achievements.compute_stats(session, user)
    settings = await reminders.get_settings(session, user)
    today = reminders.local_now(settings).date()
    finished = list(await session.scalars(
        select(WorkoutSession.finished_at)
        .where(WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_not(None))))
    days = [reminders.local_now(settings, aware(dt)).date() for dt in finished]
    weeks = goal_weeks(days, stats.week_goal, today)
    xp = earned_xp(stats.workouts, stats.prs, weeks)
    level = make_level(xp)

    # Energy and mood from the workout in progress, or the last finished one.
    catalog = await load_catalog(session)
    now = datetime.now(timezone.utc)
    active = await workouts.get_active(session, user)
    hours, had_pr = None, False
    if active is not None:
        energy_now = _session_energy_left(active, catalog)
    else:
        last = await session.scalar(
            select(WorkoutSession).where(WorkoutSession.user_id == user.id,
                                         WorkoutSession.finished_at.is_not(None))
            .order_by(WorkoutSession.finished_at.desc()))
        if last is None:
            energy_now = 100
        else:
            hours = (now - aware(last.finished_at)).total_seconds() / 3600
            had_pr = any(s.pr for s in last.sets)
            energy_now = recovered(_session_energy_left(last, catalog), hours)
    return {
        "level": level.as_dict(),
        "levels": [{"key": key, "xp": needed} for key, needed in cfg.LEVELS],
        "streak_weeks": stats.week_streak, "week_done": stats.week_done, "week_goal": stats.week_goal,
        "energy": energy_now,
        "mood": mood_for(energy_now, hours, had_pr, active is not None),
        "in_workout": active is not None,
        "stats": {"workouts": stats.workouts, "prs": stats.prs, "goal_weeks": weeks,
                  "volume_t": stats.volume_t, "protein_streak": stats.protein_streak},
        "xp_rules": {"workout": cfg.XP_PER_WORKOUT, "pr": cfg.XP_PER_PR, "goal_week": cfg.XP_PER_GOAL_WEEK},
    }


async def achievements_view(session: AsyncSession, user: User) -> dict:
    """Every achievement with progress. Anything already earned is unlocked first."""
    new = await achievements.check_new(session, user)
    stats = await achievements.compute_stats(session, user)
    have = await achievements.unlocked(session, user)
    items = []
    for a in achievements.ACHIEVEMENTS:
        row = have.get(a.code)
        items.append({
            "code": a.code, "emoji": a.emoji, "unlocked": row is not None,
            "unlocked_at": aware(row.unlocked_at).isoformat() if row is not None else None,
            "progress": min(stats.value(a.stat), a.threshold), "threshold": a.threshold,
        })
    return {"items": items, "unlocked": len(have), "total": len(items), "new": [a.code for a in new]}
