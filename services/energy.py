"""
Energy system (pure logic, no database).

- Each hard set costs energy for its muscle group. A session starts at 100 and
  the bar drains as sets are done; compound sets cost more than isolation sets.
- Weekly volume = hard sets per muscle group per week (secondary muscles count half).
- Warnings never block anything. All limits live in services/energy_config.py.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from services import energy_config as cfg


@dataclass(frozen=True)
class SetBlock:
    """The hard sets planned (or done) for one exercise."""
    muscle: str
    secondary: tuple[str, ...] = ()
    movement_type: str = "isolation"
    sets: int = 0
    timed: bool = False


def set_cost(block: SetBlock) -> float:
    """Energy one hard set of this exercise costs."""
    if block.timed:
        return cfg.SET_COST_TIMED
    return cfg.SET_COST_COMPOUND if block.movement_type == "compound" else cfg.SET_COST_ISOLATION


@dataclass(frozen=True)
class SessionLoad:
    exercises: int
    hard_sets: int
    energy_cost: int
    energy_left: int          # 0-100, what the bar shows after the whole session
    warnings: tuple[str, ...]  # text keys: too_many_exercises, too_many_sets

    @property
    def demanding(self) -> bool:
        return bool(self.warnings)

    def as_dict(self) -> dict:
        return {"exercises": self.exercises, "hard_sets": self.hard_sets,
                "energy_cost": self.energy_cost, "energy_left": self.energy_left,
                "demanding": self.demanding, "warnings": list(self.warnings)}


def session_load(blocks: list[SetBlock]) -> SessionLoad:
    """How demanding one session is, with warnings when it is too much."""
    hard_sets = sum(b.sets for b in blocks)
    cost = sum(set_cost(b) * b.sets for b in blocks)
    warnings = []
    if len(blocks) > cfg.SESSION_EXERCISES_HIGH:
        warnings.append("too_many_exercises")
    if hard_sets > cfg.SESSION_HARD_SETS_HIGH:
        warnings.append("too_many_sets")
    left = max(0, round(cfg.SESSION_ENERGY - cost))
    return SessionLoad(len(blocks), hard_sets, round(cost), left, tuple(warnings))


def energy_left(done: Iterable[tuple[SetBlock, int]]) -> int:
    """The bar during a workout: (exercise, sets completed so far) -> energy left."""
    used = sum(set_cost(block) * count for block, count in done)
    return max(0, round(cfg.SESSION_ENERGY - used))


@dataclass(frozen=True)
class MuscleVolume:
    muscle: str
    sets: float
    status: str               # low | ok | high

    def as_dict(self) -> dict:
        return {"muscle": self.muscle, "sets": self.sets, "status": self.status}


def weekly_volume(days: list[list[SetBlock]]) -> list[MuscleVolume]:
    """Hard sets per muscle group for one week of these days, most first."""
    totals: dict[str, float] = defaultdict(float)
    for day in days:
        for block in day:
            totals[block.muscle] += block.sets
            for muscle in block.secondary:
                if muscle != block.muscle:
                    totals[muscle] += block.sets * cfg.SECONDARY_MUSCLE_FACTOR
    result = []
    for muscle, sets in totals.items():
        sets = round(sets, 1)
        status = "low" if sets < cfg.WEEKLY_SETS_LOW else "high" if sets > cfg.WEEKLY_SETS_HIGH else "ok"
        result.append(MuscleVolume(muscle, sets, status))
    return sorted(result, key=lambda v: (-v.sets, v.muscle))


def limits() -> dict:
    """The limits, so the app can draw the same thresholds."""
    return {
        "session_energy": cfg.SESSION_ENERGY,
        "session_exercises_high": cfg.SESSION_EXERCISES_HIGH,
        "session_hard_sets_high": cfg.SESSION_HARD_SETS_HIGH,
        "session_hard_sets_typical": list(cfg.SESSION_HARD_SETS_TYPICAL),
        "weekly_sets_low": cfg.WEEKLY_SETS_LOW,
        "weekly_sets_high": cfg.WEEKLY_SETS_HIGH,
        "set_cost": {"compound": cfg.SET_COST_COMPOUND, "isolation": cfg.SET_COST_ISOLATION,
                     "timed": cfg.SET_COST_TIMED},
    }
