import re

import pytest

from utils.texts import EN, t

ALLOWED_TAGS = re.compile(r"</?(b|i|code)>")


def assert_valid_telegram_html(text: str) -> None:
    """Telegram rejects messages containing a bare '<', '>' or '&' outside of tags."""
    stripped = ALLOWED_TAGS.sub("", text)
    bad = [ch for ch in "<>&" if ch in stripped]
    assert not bad, f"Unescaped {bad} in: {text!r}"


@pytest.mark.parametrize("key", sorted(EN))
def test_every_text_is_valid_html(key):
    # Fill placeholders with dummy values so format() works.
    names = re.findall(r"{(\w+)}", EN[key])
    assert_valid_telegram_html(t(key, **{n: "x" for n in names}) if names else t(key))
