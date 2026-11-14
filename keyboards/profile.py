"""
Inline keyboards. Callback data uses aiogram's CallbackData factories, so
button payloads are typed and short (Telegram allows max 64 bytes).
"""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.enums import Diet, Equipment, Experience, Goal, Injury, Sex
from keyboards.food import FoodCB
from services.validation import TRAINING_DAYS_RANGE
from utils.texts import LANGUAGE_NAMES, SUPPORTED_LANGUAGES, t


class ProfileCB(CallbackData, prefix="pf"):
    """An answer to a profile question, e.g. field="goal", value="bulk"."""
    field: str
    value: str


class NavCB(CallbackData, prefix="nav"):
    """Navigation inside the profile form: back."""
    action: str


class MenuCB(CallbackData, prefix="m"):
    """Menu actions outside the form (disclaimer, settings, delete...)."""
    action: str


class EditCB(CallbackData, prefix="ed"):
    """Pick a profile field to edit."""
    field: str


def _add_back(builder: InlineKeyboardBuilder, show_back: bool) -> None:
    if show_back:
        builder.button(text=t("btn_back"), callback_data=NavCB(action="back"))


def choice_keyboard(field: str, options: list[tuple[str, str]], columns: int,
                    show_back: bool) -> InlineKeyboardMarkup:
    """options: list of (value, label)."""
    builder = InlineKeyboardBuilder()
    for value, label in options:
        builder.button(text=label, callback_data=ProfileCB(field=field, value=value))
    _add_back(builder, show_back)
    sizes = [columns] * ((len(options) + columns - 1) // columns)
    builder.adjust(*sizes, 1)
    return builder.as_markup()


def step_keyboard(step: str, show_back: bool,
                  selected_injuries: list[str] | None = None) -> InlineKeyboardMarkup | None:
    """The keyboard for each onboarding step. Typed steps only get a Back button."""
    if step == "goal":
        return choice_keyboard(step, [(g.value, t(f"goal_{g.value}")) for g in Goal], 1, show_back)
    if step == "sex":
        return choice_keyboard(step, [(s.value, t(f"sex_{s.value}")) for s in Sex], 2, show_back)
    if step == "experience":
        return choice_keyboard(
            step, [(e.value, t(f"experience_{e.value}")) for e in Experience], 1, show_back
        )
    if step == "training_days":
        low, high = TRAINING_DAYS_RANGE
        return choice_keyboard(step, [(str(d), str(d)) for d in range(low, high + 1)], 5, show_back)
    if step == "equipment":
        return choice_keyboard(
            step, [(e.value, t(f"equipment_{e.value}")) for e in Equipment], 1, show_back
        )
    if step == "diet":
        return choice_keyboard(step, [(d.value, t(f"diet_{d.value}")) for d in Diet], 2, show_back)
    if step == "injuries":
        return injuries_keyboard(selected_injuries or [], show_back)
    # Typed answers (age, height, weight).
    if show_back:
        builder = InlineKeyboardBuilder()
        _add_back(builder, True)
        return builder.as_markup()
    return None


def injuries_keyboard(selected: list[str], show_back: bool) -> InlineKeyboardMarkup:
    """Multi-select: tapping an injury toggles a ✅ next to it."""
    builder = InlineKeyboardBuilder()
    for injury in Injury:
        mark = "✅ " if injury.value in selected else ""
        builder.button(
            text=mark + t(f"injury_{injury.value}"),
            callback_data=ProfileCB(field="injuries", value=injury.value),
        )
    builder.button(text=t("btn_none"), callback_data=ProfileCB(field="injuries", value="none"))
    builder.button(text=t("btn_done"), callback_data=ProfileCB(field="injuries", value="done"))
    _add_back(builder, show_back)
    builder.adjust(2, 2, 1, 2, 1)
    return builder.as_markup()


def disclaimer_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_accept_disclaimer"), callback_data=MenuCB(action="accept_disclaimer"))
    builder.button(text=t("btn_language"), callback_data=MenuCB(action="language"))
    builder.adjust(1)
    return builder.as_markup()


def profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_edit_profile"), callback_data=MenuCB(action="edit"))
    builder.button(text=t("btn_log_food"), callback_data=FoodCB(a="menu"))
    builder.adjust(2)
    return builder.as_markup()


def settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_edit_profile"), callback_data=MenuCB(action="edit"))
    builder.button(text=t("btn_language"), callback_data=MenuCB(action="language"))
    builder.button(text=t("btn_disclaimer"), callback_data=MenuCB(action="show_disclaimer"))
    builder.button(text=t("btn_delete_data"), callback_data=MenuCB(action="delete"))
    builder.adjust(1)
    return builder.as_markup()


def edit_fields_keyboard(fields: tuple[str, ...]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name in fields:
        builder.button(text=t(f"field_{name}"), callback_data=EditCB(field=name))
    builder.button(text=t("btn_back_to_profile"), callback_data=MenuCB(action="profile"))
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_delete_confirm"), callback_data=MenuCB(action="delete_yes"))
    builder.button(text=t("btn_delete_cancel"), callback_data=MenuCB(action="delete_no"))
    builder.adjust(1)
    return builder.as_markup()


class LangCB(CallbackData, prefix="lang"):
    code: str


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in SUPPORTED_LANGUAGES:
        builder.button(text=LANGUAGE_NAMES[code], callback_data=LangCB(code=code))
    builder.adjust(1)
    return builder.as_markup()
