"""
Program rules (pure logic, no database): what each training goal means for
reps and rest, the built-in programs on the "Available" tab, default training
weekdays, session-length estimates and editor limits. Tune the numbers here.
"""
from dataclasses import dataclass, replace
from typing import Iterable

from services.plan_generator import SPLITS, PlanSpec, PlannedExercise

GOALS = ("strength", "hypertrophy", "endurance")
DEFAULT_GOAL = "hypertrophy"
DEFAULT_WEEKS = 8
WEEKS_RANGE = (4, 16)
DAYS_RANGE = (2, 6)            # workouts per week when creating a program
MAX_DAYS = 7                   # days in the split editor
MAX_EXERCISES_PER_DAY = 12
MAX_PROGRAMS = 20              # programs per user (privacy: store only what's needed)
SETS_RANGE = (1, 10)
REPS_RANGE = (1, 50)
TIMED_RANGE = (10, 180)        # seconds, for holds like the plank
REST_RANGE = (15, 600)


@dataclass(frozen=True)
class GoalRule:
    compound_reps: tuple[int, int] | None    # None = keep the plan generator's choice
    isolation_reps: tuple[int, int] | None
    compound_rest: int | None                # seconds
    isolation_rest: int | None
    rpe: tuple[int, int]                     # how hard sets should feel (RPE 8 = 2 reps left)
    volume_trend: str                        # "steady" or "progressive" (text key in the app)


# Moderate, common-sense ranges. Hypertrophy keeps the generator's defaults
# (compounds 6-12, isolation 10-15).
GOAL_RULES: dict[str, GoalRule] = {
    "strength": GoalRule((4, 6), (8, 12), 180, 90, (7, 9), "steady"),
    "hypertrophy": GoalRule(None, None, None, None, (7, 9), "progressive"),
    "endurance": GoalRule((12, 20), (15, 20), 75, 45, (6, 8), "progressive"),
}


def adjust_for_goal(item: PlannedExercise, exercise, goal: str) -> PlannedExercise:
    """Reps and rest for the program's goal. Holds and bodyweight moves keep their reps."""
    rule = GOAL_RULES.get(goal, GOAL_RULES[DEFAULT_GOAL])
    if item.timed or exercise is None or getattr(exercise, "equipment", "") == "bodyweight":
        return item
    compound = getattr(exercise, "movement_type", "") == "compound"
    reps = rule.compound_reps if compound else rule.isolation_reps
    rest = rule.compound_rest if compound else rule.isolation_rest
    if reps is None and rest is None:
        return item
    return replace(item,
                   rep_min=reps[0] if reps else item.rep_min,
                   rep_max=reps[1] if reps else item.rep_max,
                   rest_seconds=rest if rest is not None else item.rest_seconds)


def apply_goal(spec: PlanSpec, goal: str, catalog: dict) -> PlanSpec:
    """Adjust a generated plan for the goal (in place; also returned)."""
    for day in spec.days:
        day.exercises = [adjust_for_goal(item, catalog.get(item.exercise_id), goal)
                         for item in day.exercises]
    return spec


@dataclass(frozen=True)
class Template:
    """A built-in program on the "Available" tab (the app translates template_<key>)."""
    key: str
    days: int
    goal: str = DEFAULT_GOAL
    weeks: int = DEFAULT_WEEKS

    @property
    def split(self) -> str:
        return SPLITS[self.days][0]


TEMPLATES: dict[str, Template] = {t.key: t for t in (
    Template("full_body_2", 2),
    Template("full_body_3", 3),
    Template("strength_3", 3, "strength", 6),
    Template("upper_lower_4", 4),
    Template("upper_lower_ppl_5", 5),
    Template("ppl_6", 6),
)}

# Training weekdays (0 = Monday) when the user hasn't picked days in Reminders.
DEFAULT_WEEKDAYS = {1: (0,), 2: (0, 3), 3: (0, 2, 4), 4: (0, 1, 3, 4), 5: (0, 1, 2, 3, 4),
                    6: (0, 1, 2, 3, 4, 5), 7: (0, 1, 2, 3, 4, 5, 6)}


def training_weekdays(workouts_per_week: int, chosen: Iterable[int] | None = None) -> list[int]:
    """The user's workout days from Reminders if set, else a sensible spread."""
    picked = sorted({d for d in (chosen or []) if 0 <= d <= 6})
    if picked:
        return picked
    return list(DEFAULT_WEEKDAYS[min(max(workouts_per_week, 1), 7)])


WARMUP_MINUTES = 5
WORK_SECONDS_PER_SET = 40
SETUP_SECONDS_PER_EXERCISE = 60


def estimate_minutes(items: Iterable[tuple[int, int, bool, int]]) -> int:
    """Session length from (sets, rep_max, timed, rest_seconds), rounded to 5 minutes."""
    seconds = WARMUP_MINUTES * 60
    for sets, rep_max, timed, rest in items:
        work = rep_max if timed else WORK_SECONDS_PER_SET
        seconds += SETUP_SECONDS_PER_EXERCISE + sets * work + max(sets - 1, 0) * rest
    return max(10, int(5 * round(seconds / 60 / 5)))


def check_prescription(sets: int, rep_min: int, rep_max: int, rest_seconds: int, timed: bool) -> str | None:
    """None if the numbers are fine, else an error key for the app."""
    if not SETS_RANGE[0] <= sets <= SETS_RANGE[1]:
        return "bad_sets"
    low, high = TIMED_RANGE if timed else REPS_RANGE
    if not low <= rep_min <= rep_max <= high:
        return "bad_reps"
    if not REST_RANGE[0] <= rest_seconds <= REST_RANGE[1]:
        return "bad_rest"
    return None
