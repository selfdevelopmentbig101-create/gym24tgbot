"""
Which exercises a user can do, and how to find substitutes.

Rules:
- Equipment: full gym = everything. Home with dumbbells = home-friendly
  dumbbell and bodyweight exercises. Bodyweight only = home-friendly
  bodyweight exercises. (Accessories like bands or an ab wheel aren't assumed.)
- Difficulty: advanced exercises only for advanced users. Beginners may get an
  intermediate exercise, but only when no beginner option exists (see ranking).
- Injuries: exercises listed in data/injury_exclusions.json are skipped.
"""
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import Equipment, Experience
from database.models import Exercise, Profile
from services.exercise_import import load_exercises_file, load_injury_rules

DIFFICULTY_LEVEL = {"beginner": 0, "intermediate": 1, "advanced": 2}
EXPERIENCE_LEVEL = {Experience.BEGINNER: 0, Experience.INTERMEDIATE: 1, Experience.ADVANCED: 2}
HOME_EQUIPMENT = {
    Equipment.HOME_DUMBBELLS: {"dumbbell", "bodyweight"},
    Equipment.BODYWEIGHT: {"bodyweight"},
}
# Stretches and cardio live in the library but are not picked for workout plans.
PLAN_CATEGORIES = frozenset({"strength", "olympic", "plyometrics"})


def plan_ok(exercise: Exercise) -> bool:
    """Whether the plan generator may use this exercise."""
    return (getattr(exercise, "category", None) or "strength") in PLAN_CATEGORIES


@dataclass(frozen=True)
class UserFilter:
    """What we need to know about a user to choose exercises."""
    equipment: Equipment
    experience: Experience
    injuries: frozenset[str] = frozenset()

    @classmethod
    def from_profile(cls, profile: Profile) -> "UserFilter":
        return cls(Equipment(profile.equipment), Experience(profile.experience),
                   frozenset(profile.injuries or []))


@lru_cache(maxsize=1)
def get_injury_rules() -> dict[str, set[str]]:
    """Loaded once from data/injury_exclusions.json (validated against the exercise file)."""
    known_ids = {record["id"] for record in load_exercises_file()}
    return load_injury_rules(known_ids)


def equipment_ok(exercise: Exercise, equipment: Equipment) -> bool:
    if equipment == Equipment.FULL_GYM:
        return True
    return bool(exercise.home_friendly) and exercise.equipment in HOME_EQUIPMENT[equipment]


def difficulty_ok(exercise: Exercise, experience: Experience) -> bool:
    if DIFFICULTY_LEVEL[exercise.difficulty] == 2:
        return EXPERIENCE_LEVEL[experience] == 2
    return True


def difficulty_distance(exercise: Exercise, experience: Experience) -> int:
    """
    0 = ideal for the user's level, 1 = acceptable. Lower is preferred.
    Advanced lifters treat intermediate exercises as ideal too, so they aren't
    pushed into the few advanced lifts (e.g. deadlifts) every session.
    """
    level = DIFFICULTY_LEVEL[exercise.difficulty]
    user = EXPERIENCE_LEVEL[experience]
    if user == 2:
        return 0 if level >= 1 else 1
    return abs(level - user)


def injury_ok(exercise: Exercise, injuries: frozenset[str],
              rules: dict[str, set[str]] | None = None) -> bool:
    rules = get_injury_rules() if rules is None else rules
    return not any(exercise.id in rules.get(injury, ()) for injury in injuries)


def is_available(exercise: Exercise, user: UserFilter,
                 rules: dict[str, set[str]] | None = None) -> bool:
    return (
        exercise.active is not False
        and equipment_ok(exercise, user.equipment)
        and difficulty_ok(exercise, user.experience)
        and injury_ok(exercise, user.injuries, rules)
    )


def rank_key(exercise: Exercise, user: UserFilter) -> tuple[int, int, int]:
    """
    Sort key: closest difficulty first; in a full gym, prefer exercises you can
    add weight to over easy bodyweight ones; then your curated order.
    """
    easy_bodyweight = (user.equipment == Equipment.FULL_GYM
                       and exercise.equipment == "bodyweight"
                       and exercise.difficulty == "beginner")
    return (difficulty_distance(exercise, user.experience), int(easy_bodyweight),
            exercise.sort_order or 0)


def similarity(a: Exercise, b: Exercise) -> int:
    """
    How alike two exercises are, judged from substitute_ids:
    2 = list each other (same movement, e.g. barbell vs dumbbell skull crusher)
    1 = one lists the other, or they share a substitute
    0 = unrelated
    """
    subs_a, subs_b = set(a.substitute_ids or []), set(b.substitute_ids or [])
    a_lists_b, b_lists_a = b.id in subs_a, a.id in subs_b
    if a_lists_b and b_lists_a:
        return 2
    return int(a_lists_b or b_lists_a or bool(subs_a & subs_b))


def pick_substitute(current: Exercise, catalog: dict[str, Exercise], user: UserFilter,
                    exclude_ids: set[str] = frozenset(),
                    rules: dict[str, set[str]] | None = None) -> Exercise | None:
    """
    First try the curated substitute_ids (in order). If none fits the user's
    equipment/level/injuries, fall back to the same muscle group and movement type.
    """
    skip = set(exclude_ids) | {current.id}
    for sub_id in current.substitute_ids or []:
        candidate = catalog.get(sub_id)
        if candidate and sub_id not in skip and is_available(candidate, user, rules):
            return candidate

    similar = [
        ex for ex in catalog.values()
        if ex.id not in skip
        and ex.muscle_group == current.muscle_group
        and ex.movement_type == current.movement_type
        and plan_ok(ex)
        and is_available(ex, user, rules)
    ]
    return min(similar, key=lambda ex: rank_key(ex, user), default=None)


# ---------- Database helpers ----------

async def load_catalog(session: AsyncSession) -> dict[str, Exercise]:
    """All active exercises, in curated order, keyed by id."""
    rows = await session.scalars(
        select(Exercise).where(Exercise.active.is_(True)).order_by(Exercise.sort_order)
    )
    return {ex.id: ex for ex in rows}


async def get_exercise(session: AsyncSession, exercise_id: str) -> Exercise | None:
    return await session.get(Exercise, exercise_id)


async def muscle_groups(session: AsyncSession) -> list[str]:
    """Muscle groups in the order they first appear in the curated list."""
    groups: list[str] = []
    for ex in (await load_catalog(session)).values():
        if ex.muscle_group not in groups:
            groups.append(ex.muscle_group)
    return groups


async def library_exercises(session: AsyncSession, muscle_group: str,
                            profile: Profile | None) -> list[Exercise]:
    """Exercises in a muscle group the user can do (all of them if no profile yet)."""
    exercises = [ex for ex in (await load_catalog(session)).values()
                 if ex.muscle_group == muscle_group]
    if profile is None:
        return exercises
    user = UserFilter.from_profile(profile)
    return sorted((ex for ex in exercises if is_available(ex, user)),
                  key=lambda ex: rank_key(ex, user))
