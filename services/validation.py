"""
Validate and normalise user input. Each validator returns a clean value or
raises ValidationError with a text key the bot can show to the user.
"""
import re

AGE_RANGE = (16, 80)
HEIGHT_RANGE_CM = (130.0, 220.0)
WEIGHT_RANGE_KG = (35.0, 250.0)
TRAINING_DAYS_RANGE = (2, 6)

LB_TO_KG = 0.45359237
INCH_TO_CM = 2.54

_NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)\s*$")
_FEET_INCHES = re.compile(r"^\s*(\d)\s*(?:'|ft)\s*(\d{1,2})?\s*(?:\"|in)?\s*$")


class ValidationError(ValueError):
    def __init__(self, text_key: str):
        super().__init__(text_key)
        self.text_key = text_key


def _parse(text: str) -> tuple[float, str]:
    """'80,5 kg' -> (80.5, 'kg'). Raises ValidationError if it isn't a number."""
    match = _NUMBER.match(text or "")
    if not match:
        raise ValidationError("err_not_a_number")
    return float(match.group(1).replace(",", ".")), match.group(2).lower()


def validate_age(value: str | int) -> int:
    number, unit = _parse(str(value))
    if unit not in ("", "y", "yo", "yrs", "years") or number != int(number):
        raise ValidationError("err_age")
    age = int(number)
    if not AGE_RANGE[0] <= age <= AGE_RANGE[1]:
        raise ValidationError("err_age")
    return age


def validate_height(value: str | float) -> float:
    """Accepts '180', '180 cm', '1.80' (metres), '1.80m' or 5'11"."""
    text = str(value)
    feet = _FEET_INCHES.match(text)
    if feet:
        cm = (int(feet.group(1)) * 12 + int(feet.group(2) or 0)) * INCH_TO_CM
    else:
        number, unit = _parse(text)
        if unit in ("", "cm"):
            cm = number * 100 if number < 3 else number  # "1.80" means metres
        elif unit == "m":
            cm = number * 100
        else:
            raise ValidationError("err_height")
    if not HEIGHT_RANGE_CM[0] <= cm <= HEIGHT_RANGE_CM[1]:
        raise ValidationError("err_height")
    return round(cm, 1)


def validate_weight(value: str | float) -> float:
    """Accepts '80', '80.5', '80,5 kg' or '176 lb'."""
    number, unit = _parse(str(value))
    if unit in ("", "kg", "kgs"):
        kg = number
    elif unit in ("lb", "lbs"):
        kg = number * LB_TO_KG
    else:
        raise ValidationError("err_weight")
    if not WEIGHT_RANGE_KG[0] <= kg <= WEIGHT_RANGE_KG[1]:
        raise ValidationError("err_weight")
    return round(kg, 1)


def validate_training_days(value: str | int) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValidationError("err_generic") from None
    if not TRAINING_DAYS_RANGE[0] <= days <= TRAINING_DAYS_RANGE[1]:
        raise ValidationError("err_generic")
    return days
