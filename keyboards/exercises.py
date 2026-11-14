"""Keyboards for the exercise library, exercise cards and the plan."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.texts import label, t


class CardCB(CallbackData, prefix="ex"):
    """
    A button on an exercise card.
    action: "next", "sub" (substitute) or "log"
    ctx:    "lib" (browsing the library) or "day" (going through a plan day)
    ref:    muscle group for "lib", plan entry id for "day"
    ex:     the exercise currently shown (to detect outdated buttons)
    """
    action: str
    ctx: str
    ref: str
    ex: str


class LibCB(CallbackData, prefix="lib"):
    group: str  # muscle group, or "" for the group menu


class PlanCB(CallbackData, prefix="pl"):
    action: str  # "day", "overview" or "regen"
    day: int = -1


def groups_keyboard(groups: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.button(text=label("muscle", group), callback_data=LibCB(group=group))
    builder.adjust(2)
    return builder.as_markup()


def card_keyboard(ctx: str, ref: str, exercise_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for action, text_key in (("next", "btn_next"), ("sub", "btn_substitute"), ("log", "btn_log_set")):
        builder.button(text=t(text_key),
                       callback_data=CardCB(action=action, ctx=ctx, ref=ref, ex=exercise_id))
    if ctx == "lib":
        builder.button(text=t("btn_back_to_groups"), callback_data=LibCB(group=""))
    else:
        builder.button(text=t("btn_back_to_plan"), callback_data=PlanCB(action="overview"))
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def plan_keyboard(day_labels: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, day_label in enumerate(day_labels):
        builder.button(text=t("btn_day", n=index + 1, name=day_label),
                       callback_data=PlanCB(action="day", day=index))
    builder.button(text=t("btn_new_plan"), callback_data=PlanCB(action="regen"))
    n = len(day_labels)
    builder.adjust(*([2] * (n // 2)), *([1] if n % 2 else []), 1)
    return builder.as_markup()
