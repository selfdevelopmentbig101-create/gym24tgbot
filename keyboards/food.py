"""Keyboards for /food."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.foods import CATEGORIES, Food
from utils.texts import t


class FoodCB(CallbackData, prefix="fd"):
    """
    a: menu | cat | add | serv | undo | manual | edit | del | day
    v: category, food id, "entry_id|servings", entry id or day offset (0, -1, ...)
    """
    a: str
    v: str = ""


def _rows(count: int, per_row: int) -> list[int]:
    return [per_row] * (count // per_row) + ([count % per_row] if count % per_row else [])


def food_menu_keyboard(recent: list[Food], offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    sizes: list[int] = []
    if offset == 0:
        for food in recent:
            b.button(text=f"🔁 {food.name}", callback_data=FoodCB(a="add", v=food.id))
        sizes += _rows(len(recent), 2)
        for category in CATEGORIES:
            b.button(text=t(f"food_cat_{category}"), callback_data=FoodCB(a="cat", v=category))
        sizes += [3, 2]
        b.button(text=t("btn_food_manual"), callback_data=FoodCB(a="manual"))
        b.button(text=t("btn_food_edit"), callback_data=FoodCB(a="edit", v="0"))
        sizes.append(2)
    else:
        b.button(text=t("btn_food_edit"), callback_data=FoodCB(a="edit", v=str(offset)))
        sizes.append(1)
    # Day navigation: ◀ previous day, ▶ next day (not past today).
    nav = 0
    if offset > -6:
        b.button(text=t("btn_food_prev_day"), callback_data=FoodCB(a="day", v=str(offset - 1)))
        nav += 1
    if offset < 0:
        b.button(text=t("btn_food_next_day"), callback_data=FoodCB(a="day", v=str(offset + 1)))
        nav += 1
    if nav:
        sizes.append(nav)
    b.adjust(*sizes)
    return b.as_markup()


def category_keyboard(foods: list[Food]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for food in foods:
        b.button(text=food.name, callback_data=FoodCB(a="add", v=food.id))
    b.button(text=t("btn_food_back"), callback_data=FoodCB(a="menu"))
    b.adjust(*_rows(len(foods), 2), 1)
    return b.as_markup()


def logged_keyboard(entry_id: int, servings: float, from_list: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    count = 0
    if from_list:
        for option in (0.5, 1, 1.5, 2):
            mark = "• " if option == servings else ""
            b.button(text=f"{mark}×{option:g}", callback_data=FoodCB(a="serv", v=f"{entry_id}|{option:g}"))
            count += 1
    b.button(text=t("btn_undo"), callback_data=FoodCB(a="undo", v=str(entry_id)))
    b.button(text=t("btn_food_back"), callback_data=FoodCB(a="menu"))
    b.adjust(*([count] if count else []), 2)
    return b.as_markup()


def edit_keyboard(entries, offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for entry in entries:
        b.button(text=t("btn_food_delete", name=entry.name[:24], kcal=entry.kcal),
                 callback_data=FoodCB(a="del", v=str(entry.id)))
    b.button(text=t("btn_food_back"), callback_data=FoodCB(a="day", v=str(offset)))
    b.adjust(1)
    return b.as_markup()


def back_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_food_back"), callback_data=FoodCB(a="menu"))
    return b.as_markup()
