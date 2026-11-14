"""
Progressive overload suggestions ("double progression"), pure logic.

For each exercise the plan gives a rep range, e.g. 3 x 6-10:
1. Keep the weight and add reps until every set reaches the top of the range.
2. Then add the smallest weight step (2.5 kg) and start again at the bottom.
3. If you miss the bottom of the range two workouts in a row, drop ~10%
   and build back up (a mini deload).

Suggestions are deliberately small: never more than one weight step or
+5 seconds per workout.
"""
from dataclasses import dataclass, field

WEIGHT_STEP_KG = 2.5
TIMED_STEP_S = 5
MAX_TIMED_S = 120
# A sensible first-time starting weight per equipment type (0 = bodyweight).
DEFAULT_START_KG = {"barbell": 20.0, "dumbbell": 10.0, "machine": 20.0, "cable": 10.0}


@dataclass(frozen=True)
class SetResult:
    weight_kg: float
    reps: int


@dataclass(frozen=True)
class Suggestion:
    kind: str           # first | add_weight | add_reps | repeat | reduce | add_load | add_time
    weight_kg: float    # weight to put on the Log button
    reps: int           # reps (or seconds) to put on the Log button
    params: dict = field(default_factory=dict)  # values for the text (see utils/texts.py)


def round_to_step(weight: float, step: float = WEIGHT_STEP_KG) -> float:
    return max(0.0, round(weight / step) * step)


def _top_sets(sets: list[SetResult]) -> tuple[float, list[SetResult]]:
    """The heaviest weight used and the sets done with it (the 'working sets')."""
    top = max(s.weight_kg for s in sets)
    return top, [s for s in sets if s.weight_kg == top]


def suggest(previous: list[SetResult], *, rep_min: int, rep_max: int, planned_sets: int,
            equipment: str, timed: bool = False,
            before_previous: list[SetResult] | None = None) -> Suggestion:
    """
    previous: sets from the last workout with this exercise (empty if none).
    before_previous: sets from the workout before that (to spot a stall).
    """
    if not previous:
        start = DEFAULT_START_KG.get(equipment, 0.0)
        return Suggestion("first", start, rep_min, {"low": rep_min, "high": rep_max})

    weight, working = _top_sets(previous)
    all_top = len(working) >= planned_sets and all(s.reps >= rep_max for s in working)
    missed = any(s.reps < rep_min for s in working)

    if timed:
        best = max(s.reps for s in working)
        if all_top and best < MAX_TIMED_S:
            target = min(best + TIMED_STEP_S, MAX_TIMED_S)
            return Suggestion("add_time", weight, target, {"seconds": target})
        return Suggestion("repeat", weight, max(best, rep_min), {"weight": weight})

    if all_top:
        if weight == 0 and equipment == "bodyweight":
            # Can't add a plate: suggest a backpack/weight belt or a harder variation.
            return Suggestion("add_load", 0.0, rep_max, {"high": rep_max})
        new_weight = weight + WEIGHT_STEP_KG
        return Suggestion("add_weight", new_weight, rep_min,
                          {"weight": new_weight, "low": rep_min, "high": rep_max, "reps": rep_max})

    if missed:
        stalled_before = bool(before_previous) and any(
            s.reps < rep_min for s in before_previous if s.weight_kg >= weight)
        if stalled_before and weight > 0:
            lighter = round_to_step(weight * 0.9)
            if lighter < weight:
                return Suggestion("reduce", lighter, rep_min, {"weight": lighter, "low": rep_min})
        return Suggestion("repeat", weight, rep_min, {"weight": weight, "low": rep_min})

    # In range but not at the top yet: same weight, beat your weakest set by a rep.
    target = min(min(s.reps for s in working) + 1, rep_max)
    return Suggestion("add_reps", weight, target, {"weight": weight, "reps": target})
