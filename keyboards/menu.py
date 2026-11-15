"""
Reply keyboards (the main menu under the message box) and the inline
"Open Gym24" button.

Reply-keyboard buttons just send their label as a normal message, so
MenuButton matches the label in every language: a keyboard sent before a
language change keeps working.
"""
from functools import lru_cache

from aiogram.filters import Filter
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, WebAppInfo)

from config import config
from utils.texts import SUPPORTED_LANGUAGES, t

MAIN_MENU = (
    ("menu_workout", "menu_plan"),
    ("menu_exercises", "menu_progress"),
    ("menu_food", "menu_profile"),
    ("menu_settings", "menu_language"),
)
SETTINGS_MENU = (
    ("menu_reminders", "menu_language"),
    ("menu_edit_profile", "menu_about"),
    ("menu_delete", "menu_back"),
)
MENU_KEYS = frozenset(key for rows in (MAIN_MENU, SETTINGS_MENU) for row in rows for key in row)


def _reply_keyboard(rows: tuple[tuple[str, ...], ...]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(key)) for key in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(MAIN_MENU)


def settings_menu_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(SETTINGS_MENU)


@lru_cache(maxsize=1)
def _labels() -> dict[str, str]:
    """Button label (any language) -> menu key."""
    return {t(key, lang): key for key in MENU_KEYS for lang in SUPPORTED_LANGUAGES}


def menu_key(text: str | None) -> str | None:
    return _labels().get((text or "").strip())


class MenuButton(Filter):
    """Matches a tap on one of the given reply-keyboard buttons."""

    def __init__(self, *keys: str):
        unknown = set(keys) - MENU_KEYS
        if unknown:
            raise ValueError(f"Unknown menu keys: {unknown}")
        self.keys = frozenset(keys)

    async def __call__(self, message: Message) -> bool:
        return menu_key(message.text) in self.keys


def miniapp_ready() -> bool:
    return config.miniapp_url.startswith("https://")


def open_app_keyboard(path: str = "") -> InlineKeyboardMarkup | None:
    """
    Inline button that opens Gym24. Inline web_app buttons (like the menu button)
    send signed initData; reply-keyboard ones don't, so the app is never opened
    from the reply keyboard. None when MINIAPP_URL isn't an HTTPS address.
    """
    if not miniapp_ready():
        return None
    url = config.miniapp_url + ("/" + path.lstrip("/") if path else "/")
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_open_gym24"), web_app=WebAppInfo(url=url))
    ]])


async def send_main_menu(message: Message, text: str) -> None:
    """Show the reply-keyboard menu, then (if configured) the Open Gym24 button."""
    await message.answer(text, reply_markup=main_menu_keyboard())
    app_button = open_app_keyboard()
    if app_button is not None:
        await message.answer(t("app_promo"), reply_markup=app_button)
