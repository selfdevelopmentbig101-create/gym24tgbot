"""Guided workout texts: English, Russian and Uzbek have the same keys and {placeholders}."""
import json
import re
from pathlib import Path

import pytest

I18N = Path(__file__).resolve().parent.parent / "miniapp" / "src" / "i18n"


def _load(name: str) -> dict:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        dupes = {k for k in keys if keys.count(k) > 1}
        assert not dupes, f"{name} has duplicate keys: {dupes}"
        return dict(pairs)
    return json.loads((I18N / name).read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


@pytest.mark.parametrize("lang", ["en", "ru", "uz"])
def test_guided_files_have_no_duplicate_keys(lang):
    assert _load(f"guided.{lang}.json")


@pytest.mark.parametrize("lang", ["ru", "uz"])
def test_guided_translations_match_english(lang):
    en, other = _load("guided.en.json"), _load(f"guided.{lang}.json")
    assert set(en) == set(other)
    for key, text in en.items():
        assert _placeholders(text) == _placeholders(other[key]), f"{lang}: {key}"


def test_guided_keys_do_not_clash_with_other_english_files():
    guided = set(_load("guided.en.json"))
    for path in I18N.glob("*.en.json"):
        if path.name != "guided.en.json":
            assert not guided & set(_load(path.name)), path.name
    assert not guided & set(_load("en.json"))
