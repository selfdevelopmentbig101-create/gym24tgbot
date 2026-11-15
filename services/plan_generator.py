"""
Workout plan generator (pure logic, no database or Telegram).

1. Choose a split from training days:
   2-3 days: full body · 4: upper/lower · 5: upper/lower + push/pull/legs · 6: push/pull/legs x2
2. Each day is a list of slots ("a compound chest exercise", "a biceps isolation"...).
3. Each slot gets the best available exercise for the user: right equipment,
   safe for their injuries, closest to their level (beginner exercises first),
   and different from what's already in the plan when possible, so day A and
   day B aren't identical.
"""
import logging
from collections import Counter
from dataclasses import dataclass, field

from database.enums import Experience
from database.models import Exercise
from services.exercises import UserFilter, is_available, rank_key, similarity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Slot:
    muscle: str
    kind: str = "any"  # "compound", "isolation" or "any"


C, I = "compound", "isolation"

# Slots are ordered by importance; beginners get the first 6, others 7.
DAY_TEMPLATES: dict[str, list[Slot]] = {
    "full_body_a": [Slot("quads", C), Slot("chest", C), Slot("back", C), Slot("hamstrings"),
                    Slot("shoulders", I), Slot("triceps", I), Slot("core")],
    "full_body_b": [Slot("hamstrings", C), Slot("back", C), Slot("shoulders", C), Slot("glutes"),
                    Slot("chest"), Slot("biceps", I), Slot("calves")],
    "full_body_c": [Slot("quads", C), Slot("chest", C), Slot("back", C), Slot("glutes", C),
                    Slot("shoulders"), Slot("biceps", I), Slot("core")],
    "upper": [Slot("chest", C), Slot("back", C), Slot("shoulders", C), Slot("back", C),
              Slot("chest"), Slot("biceps", I), Slot("triceps", I)],
    "lower": [Slot("quads", C), Slot("hamstrings", C), Slot("glutes", C), Slot("quads"),
              Slot("hamstrings", I), Slot("calves"), Slot("core")],
    "push": [Slot("chest", C), Slot("shoulders", C), Slot("chest", C), Slot("shoulders", I),
             Slot("triceps"), Slot("chest", I), Slot("triceps", I)],
    "pull": [Slot("back", C), Slot("back", C), Slot("back"), Slot("shoulders", I),
             Slot("biceps", I), Slot("biceps", I), Slot("core")],
    "legs": [Slot("quads", C), Slot("hamstrings", C), Slot("quads"), Slot("glutes"),
             Slot("hamstrings", I), Slot("calves"), Slot("core")],
}

# training days -> (split name, [(day template, name key, suffix)])
SPLITS: dict[int, tuple[str, list[tuple[str, str, str]]]] = {
    2: ("full_body", [("full_body_a", "full_body", "A"), ("full_body_b", "full_body", "B")]),
    3: ("full_body", [("full_body_a", "full_body", "A"), ("full_body_b", "full_body", "B"),
                      ("full_body_c", "full_body", "C")]),
    4: ("upper_lower", [("upper", "upper", "A"), ("lower", "lower", "A"),
                        ("upper", "upper", "B"), ("lower", "lower", "B")]),
    5: ("upper_lower_ppl", [("upper", "upper", ""), ("lower", "lower", ""), ("push", "push", ""),
                            ("pull", "pull", ""), ("legs", "legs", "")]),
    6: ("ppl", [("push", "push", "A"), ("pull", "pull", "A"), ("legs", "legs", "A"),
                ("push", "push", "B"), ("pull", "pull", "B"), ("legs", "legs", "B")]),
}

# If a muscle group has nothing available (e.g. hamstrings for bodyweight-only
# beginners), use a closely related group instead.
GROUP_FALLBACK = {"hamstrings": "glutes", "glutes": "hamstrings"}

# Used to top up days that came out short (small equipment + injuries).
FILLER_SLOTS = [Slot("quads"), Slot("chest"), Slot("back"), Slot("core"), Slot("triceps"),
                Slot("calves"), Slot("shoulders"), Slot("glutes"), Slot("biceps"),
                Slot("hamstrings")]

TIMED_EXERCISES = {"plank-main"}  # reps are seconds


@dataclass(frozen=True)
class PlannedExercise:
    exercise_id: str
    sets: int
    rep_min: int
    rep_max: int
    timed: bool
    rest_seconds: int


@dataclass
class PlannedDay:
    template: str
    name_key: str
    suffix: str
    exercises: list[PlannedExercise] = field(default_factory=list)


@dataclass
class PlanSpec:
    split: str
    days: list[PlannedDay]


TRAINING_GOALS = ("strength", "hypertrophy", "endurance")


def prescription(exercise: Exercise, experience: Experience,
                 goal: str = "hypertrophy") -> PlannedExercise:
    """Sets, reps and rest. Hypertrophy is the default; strength and endurance adjust it."""
    base = _hypertrophy(exercise, experience)
    easy_bodyweight = exercise.equipment == "bodyweight" and exercise.difficulty == "beginner"
    if goal == "strength" and not base.timed:
        if exercise.movement_type == "compound" and not easy_bodyweight:
            return PlannedExercise(exercise.id, max(base.sets, 4), 4, 6, False, 180)
        return PlannedExercise(exercise.id, base.sets, 8, 12, False, 90)
    if goal == "endurance":
        if base.timed:
            return PlannedExercise(exercise.id, 3, 45, 60, True, 45)
        if exercise.movement_type == "compound":
            return PlannedExercise(exercise.id, base.sets, 15, 20 if easy_bodyweight else 15, False, 75)
        return PlannedExercise(exercise.id, base.sets, 15, 20, False, 45)
    return base


def _hypertrophy(exercise: Exercise, experience: Experience) -> PlannedExercise:
    """Sets, reps and rest. Moderate volume that suits most lifters."""
    if exercise.id in TIMED_EXERCISES:
        return PlannedExercise(exercise.id, 3, 30, 45, True, 60)
    if exercise.movement_type == "compound":
        sets = 4 if experience == Experience.ADVANCED else 3
        if exercise.equipment == "bodyweight" and exercise.difficulty == "beginner":
            # Easy bodyweight moves (push-ups, squats) need more reps to be hard enough.
            reps = (8, 15) if experience == Experience.BEGINNER else (12, 20)
        else:
            reps = (8, 12) if experience == Experience.BEGINNER else (6, 10)
        rest = 120 if experience == Experience.BEGINNER else 150
        return PlannedExercise(exercise.id, sets, *reps, False, rest)
    return PlannedExercise(exercise.id, 3, 10, 15, False, 75)


def _pick(slot: Slot, muscle: str, available: list[Exercise], user: UserFilter,
          used: Counter, day: list[Exercise]) -> Exercise | None:
    day_ids = {ex.id for ex in day}
    candidates = [ex for ex in available if ex.muscle_group == muscle and ex.id not in day_ids]
    matching = [ex for ex in candidates if slot.kind in ("any", ex.movement_type)]
    pool = matching or candidates  # relax compound/isolation if nothing matches

    def score(ex: Exercise):
        level, easy_bodyweight, order = rank_key(ex, user)
        # Avoid near-duplicates on the same day (e.g. pull-ups and chin-ups).
        similar = max((similarity(ex, other) for other in day), default=0)
        if user.experience == Experience.BEGINNER:
            # Beginner exercises first, even if that means a similar movement.
            return level, similar, easy_bodyweight, used[ex.id], order
        # Experienced lifters can use any level, so variety comes first.
        return similar, level, easy_bodyweight, used[ex.id], order

    return min(pool, key=score, default=None)


def generate_plan(exercises: list[Exercise], user: UserFilter, training_days: int,
                  goal: str = "hypertrophy",
                  rules: dict[str, set[str]] | None = None) -> PlanSpec:
    days_clamped = min(max(training_days, min(SPLITS)), max(SPLITS))
    split, day_layout = SPLITS[days_clamped]
    available = [ex for ex in exercises if is_available(ex, user, rules)]
    per_day = 6 if user.experience == Experience.BEGINNER else 7

    used: Counter = Counter()
    days: list[PlannedDay] = []
    for template, name_key, suffix in day_layout:
        day = PlannedDay(template, name_key, suffix)
        chosen: list[Exercise] = []
        # Template slots first, then fillers if some slots couldn't be filled.
        for slot in DAY_TEMPLATES[template] + FILLER_SLOTS:
            if len(chosen) >= per_day:
                break
            exercise = _pick(slot, slot.muscle, available, user, used, chosen)
            if exercise is None and slot.muscle in GROUP_FALLBACK:
                exercise = _pick(slot, GROUP_FALLBACK[slot.muscle], available, user, used, chosen)
            if exercise is None:
                logger.debug("No exercise for slot %s on %s", slot, template)
                continue
            used[exercise.id] += 1
            chosen.append(exercise)
            day.exercises.append(prescription(exercise, user.experience, goal))
        days.append(day)
    return PlanSpec(split, days)
