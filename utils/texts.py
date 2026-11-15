"""
All user-facing texts live in language files: locales/en.json, ru.json, uz.json.
Texts added later can go in locales/extra/<lang>.json (same keys in every
language); they are merged over the main files, so t("key") finds them too.
Texts use Telegram HTML formatting (<b>bold</b>, <i>italic</i>).

The language for the current update is stored in a context variable, set by
LanguageMiddleware (utils/middlewares.py), so handlers just call t("key").
Code that runs outside an update (reminders) calls set_language() first.
A key missing from a translation falls back to English.
"""
import json
from contextvars import ContextVar
from datetime import date
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
EXTRA_DIR = LOCALES_DIR / "extra"
SUPPORTED_LANGUAGES = ("en", "ru", "uz")
LANGUAGE_NAMES = {"en": "🇬🇧 English", "ru": "🇷🇺 Русский", "uz": "🇺🇿 O‘zbekcha"}
DEFAULT_LANGUAGE = "en"


def _load(lang: str) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in (LOCALES_DIR / f"{lang}.json", EXTRA_DIR / f"{lang}.json"):
        if path.exists():
            texts.update(json.loads(path.read_text(encoding="utf-8")))
    return texts


LANGUAGES: dict[str, dict[str, str]] = {lang: _load(lang) for lang in SUPPORTED_LANGUAGES}
EN = LANGUAGES[DEFAULT_LANGUAGE]

_current: ContextVar[str] = ContextVar("language", default=DEFAULT_LANGUAGE)


def resolve_language(code: str | None) -> str:
    """'ru', 'ru-RU' -> 'ru'; unsupported or missing translations -> 'en'."""
    short = (code or "").lower()[:2]
    return short if short in SUPPORTED_LANGUAGES and LANGUAGES.get(short) else DEFAULT_LANGUAGE


def set_language(code: str | None) -> str:
    lang = resolve_language(code)
    _current.set(lang)
    return lang


def current_language() -> str:
    return _current.get()


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Look up a text by key and fill in {placeholders}. Falls back to English."""
    texts = LANGUAGES.get(lang or _current.get()) or EN
    template = texts.get(key) or EN.get(key) or key
    return template.format(**kwargs) if kwargs else template


def label(prefix: str, value: str, lang: str | None = None) -> str:
    """
    Text for a data value, e.g. label("muscle", "quads") -> "Quads".
    Unknown values (a new muscle group in the JSON) fall back to a tidied
    version of the value itself, so new data never breaks the bot.
    """
    key = f"{prefix}_{value.replace(' ', '_').replace('-', '_')}"
    if key in EN:
        return t(key, lang)
    return value.replace("_", " ").replace("-", " ").capitalize()


def fmt_day(day: date, with_year: bool = False) -> str:
    """14 Nov / 14 нояб. / 14-noy, using the month_<n> texts."""
    text = f"{day.day} {t(f'month_{day.month}')}"
    return f"{text} {day.year}" if with_year else text
