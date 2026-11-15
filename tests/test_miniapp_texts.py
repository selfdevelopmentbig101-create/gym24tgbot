"""Mini App text files: no duplicate keys (a later duplicate silently wins), ru matches en."""
import json
import re
from pathlib import Path

import pytest

I18N = Path(__file__).resolve().parent.parent / "miniapp" / "src" / "i18n"


def _load(lang: str) -> dict:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        dupes = {k for k in keys if keys.count(k) > 1}
        assert not dupes, f"{lang}.json has duplicate keys: {dupes}"
        return dict(pairs)
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


@pytest.mark.parametrize("lang", ["en", "ru", "uz"])
def test_no_duplicate_keys(lang):
    _load(lang)


def test_russian_has_every_english_text():
    en, ru = _load("en"), _load("ru")
    assert set(en) == set(ru)
    for key, text in en.items():
        assert set(re.findall(r"\{(\w+)\}", text)) == set(re.findall(r"\{(\w+)\}", ru[key])), key


def test_uzbek_only_uses_known_keys():
    # Uzbek falls back to English for now; any key it has must exist in English.
    assert set(_load("uz")) <= set(_load("en"))
