"""
Calorie and protein calculator.

1. BMR (energy at rest) with the Mifflin-St Jeor equation.
2. TDEE = BMR x activity factor (based on training days).
3. Add a moderate surplus for the goal, inside hard safety limits.
4. Protein: 1.6-2.2 g per kg of body weight, depending on goal.
5. Fat 25% of calories (at least 0.6 g/kg); carbs fill the rest.
6. Optional goal weight -> estimated goal date at a healthy gain rate.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from database.enums import Goal, Sex

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

# goal -> (surplus as a share of TDEE, minimum kcal, maximum kcal)
GOAL_SURPLUS = {
    Goal.BULK: (0.12, 250, 500),
    Goal.LEAN_BULK: (0.07, 150, 300),
    Goal.RECOMP: (0.0, 0, 0),  # Recomposition: eat at maintenance.
}

# Recomp gets the most protein: it helps build muscle without a surplus.
GOAL_PROTEIN_G_PER_KG = {Goal.BULK: 1.8, Goal.LEAN_BULK: 2.0, Goal.RECOMP: 2.2}

# Healthy rate of weight gain, as a share of body weight per week.
GOAL_WEEKLY_GAIN = {
    Goal.BULK: (0.0025, 0.005),
    Goal.LEAN_BULK: (0.001, 0.0025),
    Goal.RECOMP: (0.0, 0.0),
}


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

    gain_low, gain_high = GOAL_WEEKLY_GAIN[goal]
    fat, carbs = split_fat_carbs(calories, int(protein), protein_weight)

    return NutritionTargets(
        bmr=round(bmr),
        tdee=round(tdee),
        surplus=calories - round(tdee),
        calories=calories,
        protein_g=int(protein),
        protein_g_per_kg=g_per_kg,
        protein_basis_kg=round(protein_weight, 1),
        weekly_gain_kg=(round(weight_kg * gain_low, 2), round(weight_kg * gain_high, 2)),
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
    to_gain_kg: float
    estimated_date: date   # at the middle of the healthy gain rate
    earliest_date: date    # at the fastest healthy rate
    latest_date: date      # at the slowest healthy rate


def estimate_goal_date(weight_kg: float, target_weight_kg: float | None,
                       weekly_gain_kg: tuple[float, float], today: date) -> GoalEstimate | None:
    """None when there's no target, it's already reached, or the goal gains no weight (recomp)."""
    low, high = weekly_gain_kg
    if target_weight_kg is None or target_weight_kg <= weight_kg or low <= 0 or high <= 0:
        return None
    to_gain = target_weight_kg - weight_kg

    def after(rate: float) -> date:
        return today + timedelta(days=round(to_gain / rate * 7))

    return GoalEstimate(target_weight_kg=round(target_weight_kg, 1), to_gain_kg=round(to_gain, 1),
                        estimated_date=after((low + high) / 2), earliest_date=after(high),
                        latest_date=after(low))


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
