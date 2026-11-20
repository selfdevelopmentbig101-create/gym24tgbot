from datetime import date, timedelta

import pytest

from database.enums import Goal, Sex
from services.nutrition import (
    MAX_DEFICIT_KCAL,
    MAX_SURPLUS_KCAL,
    PROTEIN_MAX_G_PER_KG,
    PROTEIN_MIN_G_PER_KG,
    bmr_mifflin_st_jeor,
    calculate_targets,
    estimate_goal_date,
    target_weight_fits,
)


def test_bmr_matches_mifflin_st_jeor():
    # 10*80 + 6.25*180 - 5*30 + 5 = 1780
    assert bmr_mifflin_st_jeor(80, 180, 30, Sex.MALE) == 1780
    # 10*60 + 6.25*165 - 5*25 - 161 = 1345.25
    assert bmr_mifflin_st_jeor(60, 165, 25, Sex.FEMALE) == pytest.approx(1345.25)


def test_typical_lean_bulk():
    r = calculate_targets(weight_kg=80, height_cm=180, age=30, sex=Sex.MALE,
                          training_days=4, goal=Goal.LEAN_BULK)
    assert r.bmr == 1780
    assert r.tdee == 2670            # 1780 * 1.5
    assert 150 <= r.surplus <= 300   # lean bulk surplus band
    assert r.calories == 2860        # 2670 + 187 surplus, rounded to 10
    assert r.protein_g == 160        # 80 kg * 2.0 g/kg
    assert r.notes == []


@pytest.mark.parametrize("goal", list(Goal))
@pytest.mark.parametrize("sex", list(Sex))
@pytest.mark.parametrize("weight,height,age,days", [
    (35, 130, 16, 2), (55, 160, 20, 3), (80, 180, 30, 4), (120, 175, 45, 6), (250, 220, 80, 6),
])
def test_safety_limits_hold_for_all_inputs(goal, sex, weight, height, age, days):
    r = calculate_targets(weight_kg=weight, height_cm=height, age=age, sex=sex,
                          training_days=days, goal=goal)
    assert r.surplus <= MAX_SURPLUS_KCAL + 5  # +5 for rounding to 10 kcal
    assert r.calories >= r.bmr - 5            # never eat below resting needs
    assert PROTEIN_MIN_G_PER_KG <= r.protein_g_per_kg <= PROTEIN_MAX_G_PER_KG
    assert r.protein_g <= weight * PROTEIN_MAX_G_PER_KG + 5


def test_recomp_is_maintenance():
    r = calculate_targets(weight_kg=75, height_cm=178, age=28, sex=Sex.MALE,
                          training_days=3, goal=Goal.RECOMP)
    assert abs(r.calories - r.tdee) <= 5
    assert r.weekly_gain_kg == (0.0, 0.0)


def test_bulk_surplus_is_capped():
    r = calculate_targets(weight_kg=140, height_cm=210, age=20, sex=Sex.MALE,
                          training_days=6, goal=Goal.BULK)
    assert r.surplus <= 505


def test_high_bmi_uses_reference_weight_and_suggests_lean_bulk():
    r = calculate_targets(weight_kg=120, height_cm=175, age=35, sex=Sex.MALE,
                          training_days=3, goal=Goal.BULK)
    assert "note_high_bmi_bulk" in r.notes
    assert r.protein_g < 120 * 1.8  # based on BMI-27 weight (~82.7 kg), not 120 kg
    assert r.protein_basis_kg == pytest.approx(82.7, abs=0.1)


def test_under_18_note():
    r = calculate_targets(weight_kg=60, height_cm=170, age=16, sex=Sex.MALE,
                          training_days=3, goal=Goal.LEAN_BULK)
    assert "note_under_18" in r.notes


def test_weight_loss_goal_runs_a_deficit_and_loses_weight():
    r = calculate_targets(weight_kg=80, height_cm=170, age=30, sex=Sex.FEMALE,
                          training_days=3, goal=Goal.LOSE_WEIGHT)
    assert -MAX_DEFICIT_KCAL - 5 <= r.surplus < 0
    low, high = r.weekly_gain_kg
    assert low < high < 0                    # both rates are losses
    assert r.protein_g_per_kg == 2.2         # high protein protects muscle


def test_goal_date_counts_down_for_weight_loss():
    today = date(2026, 1, 1)
    goal = estimate_goal_date(80, 75, (-0.8, -0.4), today)
    assert goal.to_gain_kg == -5
    assert goal.earliest_date < goal.estimated_date < goal.latest_date
    assert goal.earliest_date > today
    # The target itself sets the direction: 85 > 80 means gain, even for a loss goal.
    gain = estimate_goal_date(80, 85, (-0.8, -0.4), today)
    assert gain.to_gain_kg == 5 and gain.earliest_date > today


def test_target_weight_can_be_anywhere_in_the_allowed_range():
    assert target_weight_fits(Goal.LOSE_WEIGHT, 80, 75)
    assert target_weight_fits(Goal.LOSE_WEIGHT, 80, 85)     # above current: gain
    assert target_weight_fits(Goal.LEAN_BULK, 80, 85)
    assert target_weight_fits(Goal.LEAN_BULK, 80, 75)       # below current: lose
    assert not target_weight_fits(Goal.RECOMP, 80, 75)      # maintenance: no goal weight
    assert not target_weight_fits(Goal.LOSE_WEIGHT, 80, 34)
    assert not target_weight_fits(Goal.LOSE_WEIGHT, 80, 201)
    assert target_weight_fits(Goal.LOSE_WEIGHT, 80, None)
