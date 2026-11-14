"""Keyboards for /progress, /weight, /measure and /reminders."""
from datetime import datetime, timedelta, timezone

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.body import MEASUREMENT_KINDS
from services.reminders import OFFSETS_MINUTES, REMINDER_HOURS
from utils.texts import t


class ProgCB(CallbackData, prefix="pg"):
    """a: action, v: value (weight, 'kind|value', chart type), r: chart range in days."""
    a: str
    v: str = ""
    r: int = 0


class RemCB(CallbackData, prefix="rm"):
    a: str
    v: str = ""


# ---------- Progress ----------

def progress_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_log_weight"), callback_data=ProgCB(a="wlog"))
    b.button(text=t("btn_log_measurement"), callback_data=ProgCB(a="mlog"))
    b.button(text=t("btn_chart_weight"), callback_data=ProgCB(a="chart", v="weight", r=30))
    b.button(text=t("btn_chart_strength"), callback_data=ProgCB(a="strength"))
    b.button(text=t("btn_chart_volume"), callback_data=ProgCB(a="chart", v="volume", r=7))
    b.button(text=t("btn_chart_measure"), callback_data=ProgCB(a="chart", v="measure", r=30))
    b.button(text=t("btn_prs"), callback_data=ProgCB(a="prs"))
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def back_to_progress() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_back_to_progress"), callback_data=ProgCB(a="menu"))
    return b.as_markup()


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def weight_keyboard(value: float) -> InlineKeyboardMarkup:
    """Every button carries its resulting value, so no draft needs storing."""
    b = InlineKeyboardBuilder()
    for delta in (-0.5, -0.1, 0.1, 0.5):
        b.button(text=f"{delta:+.1f}", callback_data=ProgCB(a="wset", v=_fmt(value + delta)))
    b.button(text=t("btn_save_weight", value=_fmt(value)), callback_data=ProgCB(a="wsave", v=_fmt(value)))
    b.button(text=t("btn_back_to_progress"), callback_data=ProgCB(a="menu"))
    b.adjust(4, 1, 1)
    return b.as_markup()


def measure_kinds_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for kind in MEASUREMENT_KINDS:
        b.button(text=t(f"measure_{kind}"), callback_data=ProgCB(a="mkind", v=kind))
    b.button(text=t("btn_back_to_progress"), callback_data=ProgCB(a="menu"))
    b.adjust(3, 2, 1)
    return b.as_markup()


def measure_keyboard(kind: str, value: float) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for delta in (-1, -0.5, 0.5, 1):
        b.button(text=f"{delta:+g}", callback_data=ProgCB(a="mset", v=f"{kind}|{_fmt(value + delta)}"))
    b.button(text=t("btn_save_measure", value=_fmt(value)),
             callback_data=ProgCB(a="msave", v=f"{kind}|{_fmt(value)}"))
    b.button(text=t("btn_back_to_progress"), callback_data=ProgCB(a="menu"))
    b.adjust(4, 1, 1)
    return b.as_markup()


def chart_keyboard(chart: str, days: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for label_key, value in (("btn_week", 7), ("btn_month", 30)):
        mark = "• " if value == days else ""
        b.button(text=mark + t(label_key), callback_data=ProgCB(a="chart", v=chart, r=value))
    b.button(text=t("btn_back_to_progress"), callback_data=ProgCB(a="menu"))
    b.adjust(2, 1)
    return b.as_markup()


def strength_keyboard(exercises) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ex in exercises:
        b.button(text=ex.name, callback_data=ProgCB(a="chart", v=f"s.{ex.id}", r=30))
    b.button(text=t("btn_back_to_progress"), callback_data=ProgCB(a="menu"))
    b.adjust(*([2] * ((len(exercises) + 1) // 2)), 1)
    return b.as_markup()


# ---------- Reminders ----------

def timezone_keyboard(now: datetime | None = None) -> InlineKeyboardMarkup:
    """One button per UTC offset, labelled with the local time there right now."""
    now = now or datetime.now(timezone.utc)
    b = InlineKeyboardBuilder()
    for minutes in OFFSETS_MINUTES:
        local = now + timedelta(minutes=minutes)
        b.button(text=local.strftime("%H:%M"), callback_data=RemCB(a="tz", v=str(minutes)))
    b.adjust(5)
    return b.as_markup()


def reminders_keyboard(settings) -> InlineKeyboardMarkup:
    on, off = t("state_on"), t("state_off")
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_rem_workout", state=on if settings.workout_enabled else off),
             callback_data=RemCB(a="wtoggle"))
    b.button(text=t("btn_rem_days"), callback_data=RemCB(a="days"))
    b.button(text=t("btn_rem_time", time=settings.workout_time), callback_data=RemCB(a="time", v="workout"))
    b.button(text=t("btn_rem_weighin", state=t(f"weighin_{settings.weighin_mode}")),
             callback_data=RemCB(a="wimode"))
    b.button(text=t("btn_rem_weighin_day", day=t(f"weekday_{settings.weighin_day}")),
             callback_data=RemCB(a="widay"))
    b.button(text=t("btn_rem_time", time=settings.weighin_time), callback_data=RemCB(a="time", v="weighin"))
    b.button(text=t("btn_rem_nudge", state=on if settings.nudge_enabled else off),
             callback_data=RemCB(a="ntoggle"))
    b.button(text=t("btn_rem_time", time=settings.nudge_time), callback_data=RemCB(a="time", v="nudge"))
    b.button(text=t("btn_rem_tz"), callback_data=RemCB(a="tzpick"))
    b.button(text=t("btn_rem_all_off"), callback_data=RemCB(a="alloff"))
    b.adjust(3, 3, 2, 2)
    return b.as_markup()


def time_keyboard(field: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for hour in REMINDER_HOURS:
        value = f"{hour:02d}:00"
        # ":" is reserved in callback data, so the time travels as "0700".
        b.button(text=value, callback_data=RemCB(a="settime", v=f"{field}|{hour:02d}00"))
    b.button(text=t("btn_back"), callback_data=RemCB(a="view"))
    b.adjust(5, 5, 5, 4, 1)
    return b.as_markup()


def days_keyboard(selected: list[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for day in range(7):
        mark = "✅ " if day in selected else ""
        b.button(text=mark + t(f"weekday_{day}"), callback_data=RemCB(a="day", v=str(day)))
    b.button(text=t("btn_done"), callback_data=RemCB(a="view"))
    b.adjust(4, 3, 1)
    return b.as_markup()


def nudge_keyboard(workout_time: str, fewer_days: int | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_resched_tomorrow", time=workout_time), callback_data=RemCB(a="resched", v="1"))
    b.button(text=t("btn_resched_2days"), callback_data=RemCB(a="resched", v="2"))
    b.button(text=t("btn_resched_skip"), callback_data=RemCB(a="skip"))
    if fewer_days:
        b.button(text=t("btn_fewer_days", n=fewer_days), callback_data=RemCB(a="fewer", v=str(fewer_days)))
    b.adjust(1)
    return b.as_markup()
