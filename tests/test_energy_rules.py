"""Stage 4 pure rules: energy bar, weekly volume, goals, weekdays, session length."""
from types import SimpleNamespace

from services import energy, energy_config as cfg
from services import program_rules as rules
from services.energy import SetBlock
from services.plan_generator import PlannedExercise


def _blocks(count, sets=3, kind="compound"):
    return [SetBlock(f"m{i % 3}", ("triceps",), kind, sets) for i in range(count)]


def test_normal_session_has_no_warning():
    load = energy.session_load(_blocks(6))
    assert load.hard_sets == 18 and load.warnings == () and 0 < load.energy_left < 100


def test_big_session_warns_but_is_not_blocked():
    load = energy.session_load(_blocks(9))            # 9 exercises, 27 hard sets
    assert set(load.warnings) == {"too_many_exercises", "too_many_sets"}
    assert load.demanding and load.energy_left == 0


def test_energy_drains_with_completed_sets():
    a, b = _blocks(2)
    assert energy.energy_left([]) == cfg.SESSION_ENERGY
    assert energy.energy_left([(a, 3), (b, 1)]) == round(cfg.SESSION_ENERGY - 4 * cfg.SET_COST_COMPOUND)


def test_weekly_volume_counts_secondary_muscles_half():
    week = [[SetBlock("chest", ("triceps",), "compound", 4)],
            [SetBlock("chest", (), "compound", 4), SetBlock("triceps", (), "isolation", 3)]]
    volume = {v.muscle: v for v in energy.weekly_volume(week)}
    assert volume["chest"].sets == 8 and volume["chest"].status == "low"
    assert volume["triceps"].sets == 5
    big = energy.weekly_volume([[SetBlock("back", (), "compound", 11)]] * 2)
    assert big[0].status == "high" and big[0].sets == 22


def test_goal_changes_reps_and_rest():
    item = PlannedExercise("x", 3, 8, 12, False, 120)
    barbell = SimpleNamespace(movement_type="compound", equipment="barbell")
    strength = rules.adjust_for_goal(item, barbell, "strength")
    assert (strength.rep_min, strength.rep_max, strength.rest_seconds) == (4, 6, 180)
    assert rules.adjust_for_goal(item, barbell, "hypertrophy") == item
    pushup = SimpleNamespace(movement_type="compound", equipment="bodyweight")
    assert rules.adjust_for_goal(item, pushup, "strength") == item       # bodyweight keeps reps
    plank = PlannedExercise("plank-main", 3, 30, 45, True, 60)
    assert rules.adjust_for_goal(plank, barbell, "endurance") == plank   # holds keep seconds


def test_training_weekdays_and_minutes():
    assert rules.training_weekdays(3) == [0, 2, 4]
    assert rules.training_weekdays(3, [5, 1, 1]) == [1, 5]               # days picked in Reminders
    minutes = rules.estimate_minutes([(3, 12, False, 120)] * 6)
    assert 40 <= minutes <= 50 and minutes % 5 == 0


def test_prescription_limits():
    assert rules.check_prescription(3, 8, 12, 90, False) is None
    assert rules.check_prescription(0, 8, 12, 90, False) == "bad_sets"
    assert rules.check_prescription(3, 12, 8, 90, False) == "bad_reps"
    assert rules.check_prescription(3, 30, 60, 60, True) is None          # seconds for holds
    assert rules.check_prescription(3, 8, 12, 5, False) == "bad_rest"
