import re

import pytest

from utils.texts import EN, LANGUAGES, SUPPORTED_LANGUAGES, t

ALLOWED_TAGS = re.compile(r"</?(b|i|code)>")
PLACEHOLDER = re.compile(r"{(\w+)}")


def assert_valid_telegram_html(text: str) -> None:
    """Telegram rejects messages containing a bare '<', '>' or '&' outside of tags."""
    stripped = ALLOWED_TAGS.sub("", text)
    bad = [ch for ch in "<>&" if ch in stripped]
    assert not bad, f"Unescaped {bad} in: {text!r}"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_every_language_has_every_key(lang):
    assert set(LANGUAGES[lang]) == set(EN)


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
@pytest.mark.parametrize("key", sorted(EN))
def test_every_text_is_valid_and_keeps_placeholders(lang, key):
    text = LANGUAGES[lang][key]
    assert sorted(PLACEHOLDER.findall(text)) == sorted(PLACEHOLDER.findall(EN[key])), key
    assert sorted(ALLOWED_TAGS.findall(text)) == sorted(ALLOWED_TAGS.findall(EN[key])), key
    names = PLACEHOLDER.findall(text)
    assert_valid_telegram_html(t(key, lang, **{n: "x" for n in names}) if names else text)


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_buttons_fit_on_a_phone(lang):
    # Telegram truncates long button labels; keep them short.
    long = {k: v for k, v in LANGUAGES[lang].items()
            if k.startswith("btn_") and len(PLACEHOLDER.sub("xx", v)) > 40}
    assert not long
