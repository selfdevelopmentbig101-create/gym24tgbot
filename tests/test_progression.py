import pytest

from services.progression import SetResult, suggest

S = SetResult


def run(previous, before=None, rep_min=6, rep_max=10, sets=3, equipment="barbell", timed=False):
    return suggest(previous, rep_min=rep_min, rep_max=rep_max, planned_sets=sets,
                   equipment=equipment, timed=timed, before_previous=before)


@pytest.mark.parametrize("equipment,start", [("barbell", 20), ("dumbbell", 10), ("bodyweight", 0)])
def test_first_time_uses_a_sensible_start(equipment, start):
    hint = run([], equipment=equipment)
    assert hint.kind == "first" and hint.weight_kg == start and hint.reps == 6


def test_all_sets_at_top_of_range_adds_one_weight_step():
    hint = run([S(60, 10), S(60, 10), S(60, 10)])
    assert (hint.kind, hint.weight_kg, hint.reps) == ("add_weight", 62.5, 6)


def test_top_reps_but_too_few_sets_does_not_add_weight():
    assert run([S(60, 10), S(60, 10)]).kind == "add_reps"


def test_in_range_adds_reps_to_weakest_set():
    hint = run([S(60, 10), S(60, 9), S(60, 7)])
    assert (hint.kind, hint.weight_kg, hint.reps) == ("add_reps", 60, 8)


def test_working_weight_is_the_heaviest():
    # Warm-up at 40 kg shouldn't count against the working sets.
    hint = run([S(40, 5), S(60, 10), S(60, 10), S(60, 10)])
    assert hint.kind == "add_weight" and hint.weight_kg == 62.5


def test_missed_once_repeats_the_weight():
    hint = run([S(62.5, 7), S(62.5, 6), S(62.5, 5)])
    assert (hint.kind, hint.weight_kg) == ("repeat", 62.5)


def test_missed_twice_suggests_a_10_percent_drop():
    hint = run([S(62.5, 6), S(62.5, 5), S(62.5, 5)], before=[S(62.5, 6), S(62.5, 5), S(62.5, 4)])
    assert (hint.kind, hint.weight_kg) == ("reduce", 55.0)


def test_bodyweight_at_top_suggests_load_not_weight():
    hint = run([S(0, 15), S(0, 15), S(0, 15)], rep_min=8, rep_max=15, equipment="bodyweight")
    assert hint.kind == "add_load" and hint.weight_kg == 0


def test_timed_adds_five_seconds_with_a_cap():
    assert run([S(0, 45)] * 3, rep_min=30, rep_max=45, timed=True).reps == 50
    assert run([S(0, 120)] * 3, rep_min=30, rep_max=45, timed=True).kind == "repeat"


def test_suggestions_are_never_big_jumps():
    for weight in (5, 20, 60, 140):
        hint = run([S(weight, 10)] * 3)
        assert hint.weight_kg - weight <= 2.5
