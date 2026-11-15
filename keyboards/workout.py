"""Keyboards for the workout logger."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.texts import t


class WorkoutCB(CallbackData, prefix="wk"):
    """
    a: action (overview, day, start, w, r, log, same, undo, swap, next, list, goto, card, finish)
    s: workout session id (0 before a workout starts); stale buttons are detected with it
    v: extra value (day index, weight/reps change, exercise index)
    """
    a: str
    s: int = 0
    v: str = ""


def overview_keyboard(day_index: int, day_labels: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_start_workout"), callback_data=WorkoutCB(a="start", v=str(day_index)))
    others = [(i, name) for i, name in enumerate(day_labels) if i != day_index]
    for i, name in others:
        builder.button(text=t("btn_day", n=i + 1, name=name), callback_data=WorkoutCB(a="day", v=str(i)))
    builder.adjust(1, *([2] * ((len(others) + 1) // 2)))
    return builder.as_markup()


def card_keyboard(session_id: int, *, timed: bool, log_label: str,
                  same_label: str | None) -> InlineKeyboardMarkup:
    """The logger card. Logging the pre-filled set is 1 tap; adjusting then logging is 2."""
    s = session_id
    builder = InlineKeyboardBuilder()
    sizes = []
    if timed:
        builder.button(text=t("btn_secs_minus"), callback_data=WorkoutCB(a="r", s=s, v="-5"))
        builder.button(text=t("btn_secs_plus"), callback_data=WorkoutCB(a="r", s=s, v="5"))
        sizes.append(2)
    else:
        builder.button(text=t("btn_weight_minus"), callback_data=WorkoutCB(a="w", s=s, v="-2.5"))
        builder.button(text=t("btn_weight_plus"), callback_data=WorkoutCB(a="w", s=s, v="2.5"))
        builder.button(text=t("btn_reps_minus"), callback_data=WorkoutCB(a="r", s=s, v="-1"))
        builder.button(text=t("btn_reps_plus"), callback_data=WorkoutCB(a="r", s=s, v="1"))
        sizes.append(4)
    builder.button(text=log_label, callback_data=WorkoutCB(a="log", s=s))
    sizes.append(1)
    if same_label:
        builder.button(text=same_label, callback_data=WorkoutCB(a="same", s=s))
        sizes.append(1)
    builder.button(text=t("btn_undo"), callback_data=WorkoutCB(a="undo", s=s))
    builder.button(text=t("btn_swap"), callback_data=WorkoutCB(a="swap", s=s))
    builder.button(text=t("btn_next_exercise"), callback_data=WorkoutCB(a="next", s=s))
    builder.button(text=t("btn_exercise_list"), callback_data=WorkoutCB(a="list", s=s))
    builder.button(text=t("btn_finish"), callback_data=WorkoutCB(a="finish", s=s))
    builder.adjust(*sizes, 3, 2)
    return builder.as_markup()


def exercise_list_keyboard(session_id: int, labels: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, text in enumerate(labels):
        builder.button(text=text, callback_data=WorkoutCB(a="goto", s=session_id, v=str(index)))
    builder.button(text=t("btn_back_to_card"), callback_data=WorkoutCB(a="card", s=session_id))
    builder.button(text=t("btn_finish"), callback_data=WorkoutCB(a="finish", s=session_id))
    builder.adjust(*([1] * len(labels)), 2)
    return builder.as_markup()


def rest_over_keyboard(session_id: int, label: str, action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=label, callback_data=WorkoutCB(a=action, s=session_id))
    return builder.as_markup()
