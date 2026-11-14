import pytest

from services.validation import (
    ValidationError,
    validate_age,
    validate_height,
    validate_training_days,
    validate_weight,
)


@pytest.mark.parametrize("text,expected", [("27", 27), (" 16 ", 16), ("80", 80), ("30 years", 30)])
def test_age_ok(text, expected):
    assert validate_age(text) == expected


@pytest.mark.parametrize("text", ["15", "81", "abc", "27.5", "", "-5", "25 kg"])
def test_age_rejected(text):
    with pytest.raises(ValidationError):
        validate_age(text)


@pytest.mark.parametrize("text,expected", [
    ("178", 178), ("178 cm", 178), ("1.78", 178), ("1,78m", 178), ("5'10", 177.8), ("6ft", 182.9),
])
def test_height_ok(text, expected):
    assert validate_height(text) == pytest.approx(expected, abs=0.1)


@pytest.mark.parametrize("text", ["100", "250", "tall", "180 kg", "0"])
def test_height_rejected(text):
    with pytest.raises(ValidationError):
        validate_height(text)


@pytest.mark.parametrize("text,expected", [
    ("72.5", 72.5), ("72,5", 72.5), ("80 kg", 80), ("176 lb", 79.8), ("176lbs", 79.8),
])
def test_weight_ok(text, expected):
    assert validate_weight(text) == pytest.approx(expected, abs=0.1)


@pytest.mark.parametrize("text", ["20", "300", "heavy", "80 st"])
def test_weight_rejected(text):
    with pytest.raises(ValidationError):
        validate_weight(text)


def test_training_days():
    assert validate_training_days("4") == 4
    for bad in ("1", "7", "x"):
        with pytest.raises(ValidationError):
            validate_training_days(bad)
