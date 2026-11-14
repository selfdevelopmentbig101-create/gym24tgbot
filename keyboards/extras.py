"""Keyboards for achievements, auto-adjust suggestions and admin."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.texts import t


class AdjCB(CallbackData, prefix="adj"):
    """a: deload_yes | deload_no | kcal_yes | kcal_no; v: calorie delta."""
    a: str
    v: int = 0


class AdminCB(CallbackData, prefix="adm"):
    a: str  # send | cancel


def deload_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_deload_yes"), callback_data=AdjCB(a="deload_yes"))
    b.button(text=t("btn_not_now"), callback_data=AdjCB(a="deload_no"))
    b.adjust(1)
    return b.as_markup()


def calories_keyboard(delta: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    key = "btn_kcal_up" if delta > 0 else "btn_kcal_down"
    b.button(text=t(key, kcal=abs(delta)), callback_data=AdjCB(a="kcal_yes", v=delta))
    b.button(text=t("btn_not_now"), callback_data=AdjCB(a="kcal_no"))
    b.adjust(1)
    return b.as_markup()


def broadcast_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_broadcast_send"), callback_data=AdminCB(a="send"))
    b.button(text=t("btn_broadcast_cancel"), callback_data=AdminCB(a="cancel"))
    b.adjust(1)
    return b.as_markup()
