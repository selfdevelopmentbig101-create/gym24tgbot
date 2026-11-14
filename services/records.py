"""
Personal records and estimated one-rep max (1RM).

Estimated 1RM uses the Epley formula: weight x (1 + reps / 30).
It's only reliable for sets of 1-12 reps, so higher-rep sets are ignored.
Bodyweight-only (0 kg) and timed sets have no 1RM.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, SetLog, User

MAX_E1RM_REPS = 12


def e1rm(weight_kg: float, reps: int) -> float | None:
    if weight_kg <= 0 or not 1 <= reps <= MAX_E1RM_REPS:
        return None
    return weight_kg if reps == 1 else weight_kg * (1 + reps / 30)


@dataclass
class PersonalRecord:
    exercise: Exercise
    best_e1rm: float
    best_weight: float
    best_reps: int
    achieved_at: datetime
    heaviest_kg: float


async def _weighted_sets(session: AsyncSession, user: User, exercise_id: str | None = None):
    query = select(SetLog).where(SetLog.user_id == user.id, SetLog.weight_kg > 0)
    if exercise_id:
        query = query.where(SetLog.exercise_id == exercise_id)
    return list(await session.scalars(query.order_by(SetLog.id)))


async def best_e1rm(session: AsyncSession, user: User, exercise_id: str) -> float | None:
    values = [v for s in await _weighted_sets(session, user, exercise_id)
              if (v := e1rm(s.weight_kg, s.reps)) is not None]
    return max(values, default=None)


async def personal_records(session: AsyncSession, user: User) -> list[PersonalRecord]:
    """Best estimated 1RM per exercise, strongest first."""
    best: dict[str, PersonalRecord] = {}
    for s in await _weighted_sets(session, user):
        value = e1rm(s.weight_kg, s.reps)
        record = best.get(s.exercise_id)
        if record is not None:
            record.heaviest_kg = max(record.heaviest_kg, s.weight_kg)
        if value is None:
            continue
        if record is None:
            exercise = await session.get(Exercise, s.exercise_id)
            best[s.exercise_id] = PersonalRecord(exercise, value, s.weight_kg, s.reps,
                                                 s.created_at, s.weight_kg)
        elif value > record.best_e1rm:
            record.best_e1rm, record.best_weight, record.best_reps = value, s.weight_kg, s.reps
            record.achieved_at = s.created_at
    return sorted(best.values(), key=lambda r: r.best_e1rm, reverse=True)


async def e1rm_history(session: AsyncSession, user: User, exercise_id: str,
                       since: datetime) -> list[tuple[datetime, float]]:
    """Best estimated 1RM per workout since a date, oldest first."""
    per_session: dict[int, tuple[datetime, float]] = {}
    for s in await _weighted_sets(session, user, exercise_id):
        value = e1rm(s.weight_kg, s.reps)
        created = s.created_at if s.created_at.tzinfo else s.created_at.replace(tzinfo=since.tzinfo)
        if value is None or created < since:
            continue
        if s.session_id not in per_session or value > per_session[s.session_id][1]:
            per_session[s.session_id] = (created, value)
    return sorted(per_session.values())


async def logged_exercises(session: AsyncSession, user: User, limit: int = 8) -> list[Exercise]:
    """Exercises with weighted sets, most frequently logged first."""
    counts: dict[str, int] = {}
    for s in await _weighted_sets(session, user):
        counts[s.exercise_id] = counts.get(s.exercise_id, 0) + 1
    top = sorted(counts, key=counts.get, reverse=True)[:limit]
    return [await session.get(Exercise, ex_id) for ex_id in top]
