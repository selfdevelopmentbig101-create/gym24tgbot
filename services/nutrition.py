"""
Calorie and protein calculator.

1. BMR (energy at rest) with the Mifflin-St Jeor equation.
2. TDEE = BMR x activity factor (based on training days).
3. Add a moderate surplus or deficit for the goal, inside hard safety limits.
4. Protein: 1.6-2.2 g per kg of body weight, depending on goal.
5. Fat 25% of calories (at least 0.6 g/kg); carbs fill the rest.
6. Optional goal weight -> estimated goal date at a healthy rate of change.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from database.enums import Goal, Sex
from services.validation import TARGET_WEIGHT_RANGE_KG

# Hard safety limits, also used by any future auto-adjustment (Phase 6).
MAX_SURPLUS_KCAL = 500
MAX_DEFICIT_KCAL = 500
MIN_CALORIES = {Sex.MALE: 1500, Sex.FEMALE: 1200, Sex.UNSPECIFIED: 1350}

PROTEIN_MIN_G_PER_KG = 1.6
PROTEIN_MAX_G_PER_KG = 2.2
FAT_SHARE = 0.25
FAT_MIN_G_PER_KG = 0.6

# Gym days alone don't make someone "very active", so these factors are
# deliberately conservative. Weekly weigh-ins will fine-tune the target later.
ACTIVITY_FACTORS = {2: 1.375, 3: 1.45, 4: 1.5, 5: 1.55, 6: 1.6}

# goal -> (calorie adjustment as a share of TDEE, minimum kcal, maximum kcal).
# Negative values are a deficit. The hard limits below still apply.
GOAL_SURPLUS = {
    Goal.BULK: (0.12, 250, 500),
    Goal.LEAN_BULK: (0.07, 150, 300),
    Goal.RECOMP: (0.0, 0, 0),  # Recomposition: eat at maintenance.
    Goal.LOSE_WEIGHT: (-0.15, -500, -250),
    Goal.GAIN_MUSCLE: (0.08, 150, 300),
    Goal.IMPROVE_HEALTH: (0.0, 0, 0),
    Goal.GET_IN_SHAPE: (-0.06, -300, -100),
}

# Recomp and weight-loss goals get the most protein: it protects muscle when
# calories are at maintenance or below.
GOAL_PROTEIN_G_PER_KG = {
    Goal.BULK: 1.8,
    Goal.LEAN_BULK: 2.0,
    Goal.RECOMP: 2.2,
    Goal.LOSE_WEIGHT: 2.2,
    Goal.GAIN_MUSCLE: 2.0,
    Goal.IMPROVE_HEALTH: 1.8,
    Goal.GET_IN_SHAPE: 2.1,
}

# Healthy weekly weight change, as a share of body weight per week. Negative
# values are loss. The API keeps the field name weekly_gain_kg for compatibility;
# the sign says whether the target is to gain or lose.
GOAL_WEEKLY_CHANGE = {
    Goal.BULK: (0.0025, 0.005),
    Goal.LEAN_BULK: (0.001, 0.0025),
    Goal.RECOMP: (0.0, 0.0),
    Goal.LOSE_WEIGHT: (-0.01, -0.005),
    Goal.GAIN_MUSCLE: (0.001, 0.0025),
    Goal.IMPROVE_HEALTH: (0.0, 0.0),
    Goal.GET_IN_SHAPE: (-0.005, -0.0025),
}

# Which goals the onboarding offers for each sex (the Mini App reads this from
# /api/config, so the two stay in sync).
GOALS_BY_SEX: dict[Sex, tuple[Goal, ...]] = {
    Sex.MALE: (Goal.BULK, Goal.LEAN_BULK, Goal.RECOMP),
    Sex.FEMALE: (Goal.LOSE_WEIGHT, Goal.GAIN_MUSCLE, Goal.IMPROVE_HEALTH, Goal.GET_IN_SHAPE),
    Sex.UNSPECIFIED: tuple(Goal),
}


def goal_weight_direction(goal: Goal) -> int:
    """+1 = gain weight, -1 = lose weight, 0 = maintenance (no goal weight)."""
    low, high = GOAL_WEEKLY_CHANGE[Goal(goal)]
    if high > 0:
        return 1
    if high < 0:
        return -1
    return 0


def target_weight_fits(goal: Goal, _weight_kg: float, target_weight_kg: float | None) -> bool:
    """Any goal weight in the allowed range is fine; the value itself sets the
    direction (below current = lose, above = gain). Maintenance goals keep none."""
    if target_weight_kg is None:
        return True
    if goal_weight_direction(goal) == 0:
        return False
    return TARGET_WEIGHT_RANGE_KG[0] <= target_weight_kg <= TARGET_WEIGHT_RANGE_KG[1]


@dataclass(frozen=True)
class NutritionTargets:
    bmr: int
    tdee: int
    surplus: int
    calories: int
    protein_g: int
    protein_g_per_kg: float
    # Body weight the protein target is based on (lower than actual if BMI > 30).
    protein_basis_kg: float
    weekly_gain_kg: tuple[float, float]
    # Text keys for extra advice (see utils/texts.py), e.g. "note_high_bmi_bulk".
    notes: list[str] = field(default_factory=list)
    fat_g: int = 0
    carbs_g: int = 0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def bmr_mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == Sex.MALE:
        return base + 5
    if sex == Sex.FEMALE:
        return base - 161
    return base - 78  # midpoint of +5 and -161


def activity_factor(training_days: int) -> float:
    days = int(clamp(training_days, min(ACTIVITY_FACTORS), max(ACTIVITY_FACTORS)))
    return ACTIVITY_FACTORS[days]


def bmi(weight_kg: float, height_cm: float) -> float:
    meters = height_cm / 100
    return weight_kg / (meters * meters)


def calculate_targets(
    *,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: Sex,
    training_days: int,
    goal: Goal,
    calorie_adjust: int = 0,
) -> NutritionTargets:
    """calorie_adjust: accepted auto-adjustments (see services/adjust.py), already within safe limits."""
    sex, goal = Sex(sex), Goal(goal)
    notes: list[str] = []

    bmr = bmr_mifflin_st_jeor(weight_kg, height_cm, age, sex)
    tdee = bmr * activity_factor(training_days)

    share, low, high = GOAL_SURPLUS[goal]
    surplus = clamp(tdee * share, low, high)
    surplus = clamp(surplus, -MAX_DEFICIT_KCAL, MAX_SURPLUS_KCAL)

    # Round to the nearest 10 kcal: nobody can eat more precisely than that.
    calories = round((tdee + surplus) / 10) * 10 + int(calorie_adjust)
    # Safety floor: never below BMR or a sex-based minimum.
    calories = int(max(calories, round(bmr / 10) * 10, MIN_CALORIES[sex]))

    # With a high BMI, total body weight overstates protein needs, so use the
    # weight at BMI 27 instead.
    protein_weight = weight_kg
    if bmi(weight_kg, height_cm) > 30:
        protein_weight = 27 * (height_cm / 100) ** 2
        if goal == Goal.BULK:
            notes.append("note_high_bmi_bulk")

    if age < 18:
        notes.append("note_under_18")

    g_per_kg = clamp(GOAL_PROTEIN_G_PER_KG[goal], PROTEIN_MIN_G_PER_KG, PROTEIN_MAX_G_PER_KG)
    protein = round(protein_weight * g_per_kg / 5) * 5  # nearest 5 g

    change_low, change_high = GOAL_WEEKLY_CHANGE[goal]
    fat, carbs = split_fat_carbs(calories, int(protein), protein_weight)

    return NutritionTargets(
        bmr=round(bmr),
        tdee=round(tdee),
        surplus=calories - round(tdee),
        calories=calories,
        protein_g=int(protein),
        protein_g_per_kg=g_per_kg,
        protein_basis_kg=round(protein_weight, 1),
        weekly_gain_kg=(round(weight_kg * change_low, 2), round(weight_kg * change_high, 2)),
        notes=notes,
        fat_g=fat,
        carbs_g=carbs,
    )


def split_fat_carbs(calories: int, protein_g: int, protein_basis_kg: float) -> tuple[int, int]:
    """
    Fat: 25% of calories, but at least 0.6 g/kg (hormone health).
    Carbs: whatever calories are left after protein (4 kcal/g) and fat (9 kcal/g).
    """
    fat = max(calories * FAT_SHARE / 9, FAT_MIN_G_PER_KG * protein_basis_kg)
    fat = round(fat / 5) * 5
    carbs = max(0, round((calories - protein_g * 4 - fat * 9) / 4 / 5) * 5)
    return int(fat), int(carbs)


@dataclass(frozen=True)
class GoalEstimate:
    target_weight_kg: float
    to_gain_kg: float       # negative = weight to lose
    estimated_date: date   # at the middle of the healthy rate
    earliest_date: date    # at the fastest healthy rate
    latest_date: date      # at the slowest healthy rate


def estimate_goal_date(weight_kg: float, target_weight_kg: float | None,
                       weekly_gain_kg: tuple[float, float], today: date) -> GoalEstimate | None:
    """None when there's no target, it's already reached, or the goal keeps weight stable."""
    low, high = weekly_gain_kg
    if target_weight_kg is None or low == 0 or high == 0:
        return None
    to_change = target_weight_kg - weight_kg
    if to_change == 0:
        return None
    distance = abs(to_change)
    # Use the goal's healthy rate of change in either direction: the target
    # itself decides whether that means losing or gaining.
    slow, fast = sorted((abs(low), abs(high)))

    def after(rate: float) -> date:
        return today + timedelta(days=round(distance / rate * 7))

    return GoalEstimate(target_weight_kg=round(target_weight_kg, 1), to_gain_kg=round(to_change, 1),
                        estimated_date=after((slow + fast) / 2), earliest_date=after(fast),
                        latest_date=after(slow))


def targets_for_profile(profile) -> NutritionTargets:
    """Convenience wrapper for a database Profile."""
    return calculate_targets(
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        sex=profile.sex,
        training_days=profile.training_days,
        goal=profile.goal,
        calorie_adjust=getattr(profile, "calorie_adjust", 0) or 0,
    )
