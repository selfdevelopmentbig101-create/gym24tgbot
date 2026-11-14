import itertools
import json

import pytest

from database.enums import Equipment, Experience, Injury
from database.models import Exercise
from services.exercise_import import EXERCISES_FILE
from services.exercises import (
    UserFilter,
    equipment_ok,
    get_injury_rules,
    pick_substitute,
    similarity,
)
from services.plan_generator import generate_plan

RECORDS = json.loads(EXERCISES_FILE.read_text())


def catalog() -> dict[str, Exercise]:
    return {r["id"]: Exercise(**r, sort_order=i, active=True) for i, r in enumerate(RECORDS)}


EXERCISES = list(catalog().values())
BY_ID = {ex.id: ex for ex in EXERCISES}
RULES = get_injury_rules()

ALL_USERS = [
    UserFilter(eq, xp, frozenset(inj))
    for eq, xp, inj in itertools.product(
        Equipment, Experience, [(), *[(i.value,) for i in Injury], tuple(i.value for i in Injury)]
    )
]


@pytest.mark.parametrize("days,split,n_days", [
    (2, "full_body", 2), (3, "full_body", 3), (4, "upper_lower", 4),
    (5, "upper_lower_ppl", 5), (6, "ppl", 6),
])
def test_split_by_days(days, split, n_days):
    plan = generate_plan(EXERCISES, UserFilter(Equipment.FULL_GYM, Experience.INTERMEDIATE), days)
    assert plan.split == split and len(plan.days) == n_days


@pytest.mark.parametrize("days", [2, 3, 4, 5, 6])
@pytest.mark.parametrize("user", ALL_USERS, ids=lambda u: f"{u.equipment.value}-{u.experience.value}-{'+'.join(sorted(u.injuries)) or 'none'}")
def test_every_plan_is_safe_and_complete(user, days):
    plan = generate_plan(EXERCISES, user, days)
    per_day = 6 if user.experience == Experience.BEGINNER else 7
    for day in plan.days:
        ids = [p.exercise_id for p in day.exercises]
        assert len(ids) == len(set(ids)), f"duplicate in {day.name_key}"
        # Even bodyweight-only users with every injury get a usable session.
        assert 4 <= len(ids) <= per_day, (day.name_key, ids)
        for ex_id in ids:
            ex = BY_ID[ex_id]
            assert equipment_ok(ex, user.equipment), ex_id
            if user.experience != Experience.ADVANCED:
                assert ex.difficulty != "advanced", ex_id
            for injury in user.injuries:
                assert ex_id not in RULES[injury], (injury, ex_id)
        for p in day.exercises:
            assert 1 <= p.rep_min < p.rep_max and p.sets in (3, 4) and p.rest_seconds >= 60


@pytest.mark.parametrize("days", [2, 3, 4, 5, 6])
def test_beginners_in_a_gym_get_only_beginner_exercises(days):
    plan = generate_plan(EXERCISES, UserFilter(Equipment.FULL_GYM, Experience.BEGINNER), days)
    difficulties = {BY_ID[p.exercise_id].difficulty for d in plan.days for p in d.exercises}
    assert difficulties == {"beginner"}


def test_intermediate_lifters_get_the_main_barbell_lifts():
    plan = generate_plan(EXERCISES, UserFilter(Equipment.FULL_GYM, Experience.INTERMEDIATE), 4)
    ids = {p.exercise_id for d in plan.days for p in d.exercises}
    assert {"bench-press", "squat", "ohp", "romanian-deadlift"} <= ids


def test_no_same_movement_twice_in_a_day_for_experienced_lifters():
    for days in (4, 5, 6):
        plan = generate_plan(EXERCISES, UserFilter(Equipment.FULL_GYM, Experience.ADVANCED), days)
        for day in plan.days:
            exs = [BY_ID[p.exercise_id] for p in day.exercises]
            pairs = [(a.id, b.id) for a, b in itertools.combinations(exs, 2) if similarity(a, b) == 2]
            assert not pairs, (day.name_key, pairs)


def test_days_with_same_template_differ():
    plan = generate_plan(EXERCISES, UserFilter(Equipment.FULL_GYM, Experience.INTERMEDIATE), 4)
    upper_a, upper_b = plan.days[0], plan.days[2]
    assert [p.exercise_id for p in upper_a.exercises] != [p.exercise_id for p in upper_b.exercises]


def test_plank_is_timed():
    plan = generate_plan(EXERCISES, UserFilter(Equipment.BODYWEIGHT, Experience.BEGINNER), 3)
    planks = [p for d in plan.days for p in d.exercises if p.exercise_id == "plank-main"]
    assert planks and all(p.timed and p.rep_max <= 60 for p in planks)


# ---------- Substitutes ----------

def test_substitute_respects_equipment():
    home = UserFilter(Equipment.HOME_DUMBBELLS, Experience.BEGINNER)
    assert pick_substitute(BY_ID["bench-press"], BY_ID, home).id == "db-bench-press"
    gym = UserFilter(Equipment.FULL_GYM, Experience.INTERMEDIATE)
    assert pick_substitute(BY_ID["bench-press"], BY_ID, gym).id == "db-bench-press"


def test_substitute_skips_excluded_and_falls_back_to_same_muscle():
    home = UserFilter(Equipment.HOME_DUMBBELLS, Experience.BEGINNER)
    # lat-pulldown's substitutes (pull-up, assisted-pull-ups) need a bar/machine.
    sub = pick_substitute(BY_ID["lat-pulldown"], BY_ID, home)
    assert sub.muscle_group == "back" and sub.movement_type == "compound"
    assert equipment_ok(sub, Equipment.HOME_DUMBBELLS)

    sub2 = pick_substitute(BY_ID["bench-press"], BY_ID, home, exclude_ids={"db-bench-press"})
    assert sub2.id == "push-up"


def test_substitute_respects_injuries():
    knee = UserFilter(Equipment.FULL_GYM, Experience.INTERMEDIATE, frozenset({"knee"}))
    sub = pick_substitute(BY_ID["leg-press"], BY_ID, knee)   # hack-squat, goblet-squat
    assert sub.id == "goblet-squat"


def test_no_substitute_returns_none():
    bodyweight = UserFilter(Equipment.BODYWEIGHT, Experience.BEGINNER)
    assert pick_substitute(BY_ID["barbell-curl"], BY_ID, bodyweight) is None
