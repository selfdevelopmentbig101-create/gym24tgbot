"""Turn profiles and targets into readable messages."""
from database.models import Profile
from services.nutrition import NutritionTargets, targets_for_profile
from utils.texts import t


def _fmt_number(value: float) -> str:
    """72.0 -> '72', 72.5 -> '72.5'."""
    return f"{value:g}"


def format_field_value(field: str, value) -> str:
    """Human label for a stored profile value, e.g. ('goal', 'lean_bulk') -> 'Lean bulk'."""
    if field in ("goal", "sex", "experience", "equipment", "diet"):
        return t(f"{field}_{getattr(value, 'value', value)}")
    if field == "injuries":
        return ", ".join(t(f"injury_{i}") for i in value) if value else t("injuries_none")
    if field == "training_days":
        return t("days_value", days=value)
    if field == "height_cm":
        return f"{_fmt_number(value)} cm"
    if field == "weight_kg":
        return f"{_fmt_number(value)} kg"
    return str(value)


def format_profile(profile: Profile) -> str:
    return t(
        "profile",
        goal=format_field_value("goal", profile.goal),
        age=profile.age,
        sex=format_field_value("sex", profile.sex),
        height=_fmt_number(profile.height_cm),
        weight=_fmt_number(profile.weight_kg),
        experience=format_field_value("experience", profile.experience),
        days=profile.training_days,
        equipment=format_field_value("equipment", profile.equipment),
        injuries=format_field_value("injuries", profile.injuries),
        diet=format_field_value("diet", profile.diet),
    )


def format_targets(targets: NutritionTargets, weight_kg: float) -> str:
    # The goal decides the wording: rounding to 10 kcal can leave a maintenance
    # goal at -1 or +2 kcal, which must still read as "maintenance".
    if targets.weekly_gain_kg[1] == 0:
        surplus_text = t("surplus_zero")
    elif targets.weekly_gain_kg[1] < 0:
        surplus_text = t("deficit_text", kcal=max(0, -targets.surplus))
    else:
        surplus_text = t("surplus_positive", kcal=max(0, targets.surplus))

    if targets.protein_basis_kg < weight_kg:
        protein_basis = t("protein_per_reference_kg", g_per_kg=targets.protein_g_per_kg,
                          basis=_fmt_number(round(targets.protein_basis_kg)))
    else:
        protein_basis = t("protein_per_kg", g_per_kg=targets.protein_g_per_kg)

    low, high = targets.weekly_gain_kg
    if high > 0:
        gain_text = t("gain_range", low=low, high=high)
    elif high < 0:
        gain_text = t("loss_range", low=abs(high), high=abs(low))
    else:
        gain_text = t("gain_recomp")

    parts = [
        t(
            "targets",
            calories=targets.calories,
            surplus_text=surplus_text,
            protein=targets.protein_g,
            protein_basis=protein_basis,
            tdee=targets.tdee,
            bmr=targets.bmr,
            gain_text=gain_text,
        )
    ]
    parts += [t(note) for note in targets.notes]
    parts.append(t("targets_footer"))
    return "\n\n".join(parts)


def format_profile_with_targets(profile: Profile) -> str:
    return format_profile(profile) + "\n\n" + format_targets(
        targets_for_profile(profile), profile.weight_kg
    )
