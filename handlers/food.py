"""
/food: log meals and see today's calories and protein vs target.

- Recent foods: 2 taps (/food -> food). Food list: 3 taps (/food -> category -> food).
- Manual entry: type "650 40" or "chicken wrap 650 40" (kcal, protein).
- The summary only reports numbers and gentle hints; no extreme advice.
"""
import html
import logging
from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.onboarding import send_or_edit
from keyboards.menu import MenuButton
from keyboards.food import (
    FoodCB,
    back_keyboard,
    category_keyboard,
    edit_keyboard,
    food_menu_keyboard,
    logged_keyboard,
)
from handlers import extras
from services import achievements, foods, meals, reminders, users
from services.body import aware
from services.foods import CATEGORIES
from services.validation import ValidationError
from utils.texts import fmt_day, t

logger = logging.getLogger(__name__)
router = Router(name="food")


class FoodForm(StatesGroup):
    manual = State()  # waiting for "kcal protein"


# ---------- Formatting ----------

def bar(value: float, target: float, width: int = 10) -> str:
    """▓▓▓▓▓▓░░░░ 62%"""
    ratio = value / target if target else 0
    filled = min(width, round(ratio * width))
    return "▓" * filled + "░" * (width - filled) + f" {round(ratio * 100)}%"


def _num(value: float) -> str:
    return f"{value:,.0f}"


def day_title(day: date, today: date) -> str:
    if day == today:
        return t("food_today")
    if day == today - timedelta(days=1):
        return t("food_yesterday")
    return f"{t(f'weekday_{day.weekday()}')} {fmt_day(day)}"


def entry_line(entry, tz_settings) -> str:
    when = reminders.local_now(tz_settings, aware(entry.logged_at))
    servings = f" ×{entry.servings:g}" if entry.servings != 1 else ""
    return t("food_entry_line", time=when.strftime("%H:%M"), name=html.escape(entry.name),
             servings=servings, kcal=entry.kcal, protein=_num(entry.protein_g))


def summary_lines(summary: meals.DaySummary, title: str, diet) -> list[str]:
    target = summary.targets
    lines = [
        t("food_summary_title", title=title),
        t("food_kcal_line", value=_num(summary.kcal), target=_num(target.calories),
          bar=bar(summary.kcal, target.calories)),
        t("food_protein_line", value=_num(summary.protein_g), target=target.protein_g,
          bar=bar(summary.protein_g, target.protein_g)),
    ]
    if summary.kcal_left >= 0:
        lines.append(t("food_left", kcal=_num(summary.kcal_left),
                       protein=_num(max(0, summary.protein_left))))
    else:
        lines.append(t("food_over", kcal=_num(-summary.kcal_left),
                       protein=_num(max(0, summary.protein_left))))
    return lines


def hint_lines(summary: meals.DaySummary, diet, evening: bool = False) -> list[str]:
    hints = []
    target = summary.targets
    if summary.protein_left >= 25:
        ideas = foods.protein_ideas(diet)
        if ideas:
            names = ", ".join(f"{f.name} ({f.protein_g:g} g)" for f in ideas)
            hints.append(t("food_hint_protein", ideas=html.escape(names)))
    if summary.kcal > target.calories * 1.15:
        hints.append(t("food_hint_over"))
    elif evening and summary.kcal < target.calories * 0.85:
        hints.append(t("food_hint_short", kcal=_num(summary.kcal_left)))
    return hints


async def food_view(session: AsyncSession, user: User, offset: int = 0):
    settings = await reminders.get_settings(session, user)
    today = reminders.local_now(settings).date()
    day = today + timedelta(days=offset)
    summary = await meals.day_summary(session, user, day)
    diet = user.profile.diet

    lines = summary_lines(summary, day_title(day, today), diet)
    if summary.entries:
        lines += [""] + [entry_line(e, settings) for e in summary.entries]
    else:
        lines += ["", t("food_nothing_yet" if offset == 0 else "food_nothing_day")]
    if offset == 0:
        average = await meals.week_average(session, user, today)
        if average:
            lines += ["", t("food_week_avg", kcal=_num(average[0]), protein=average[1], days=average[2])]
        hints = hint_lines(summary, diet)
        if hints:
            lines += [""] + hints
        lines += ["", t("food_manual_tip")]
    recent = await meals.recent_foods(session, user, diet) if offset == 0 else []
    return "\n".join(lines), food_menu_keyboard(recent, offset)


async def _user(event, session: AsyncSession) -> User | None:
    user = await users.get_user(session, event.from_user.id)
    if user is None or user.profile is None:
        if isinstance(event, CallbackQuery):
            await event.answer()
        await send_or_edit(event, t("need_profile"))
        return None
    return user


def _offset(value: str) -> int | None:
    try:
        offset = int(value)
    except ValueError:
        return None
    return offset if -meals.HISTORY_DAYS < offset <= 0 else None


async def _logged_view(session: AsyncSession, user: User, entry) -> tuple[str, object]:
    food = foods.get_food(entry.food_id) if entry.food_id else None
    serving = f" ({html.escape(food.serving)})" if food else ""
    servings = f" ×{entry.servings:g}" if entry.servings != 1 else ""
    summary = await meals.day_summary(session, user, entry.day)
    lines = [t("food_logged", name=html.escape(entry.name), serving=serving, servings=servings,
               kcal=entry.kcal, protein=_num(entry.protein_g)), ""]
    lines += summary_lines(summary, t("food_today"), user.profile.diet)
    # Hitting protein can complete a protein-streak achievement.
    new = await achievements.check_new(session, user)
    if new:
        lines += ["", extras.new_achievements_text(new)]
    return "\n".join(lines), logged_keyboard(entry.id, entry.servings, food is not None)


# ---------- Commands ----------

@router.message(Command("food"))
@router.message(MenuButton("menu_food"))
async def cmd_food(message: Message, session: AsyncSession, state: FSMContext,
                   command: CommandObject | None = None) -> None:
    user = await _user(message, session)
    if user is None:
        return
    await state.clear()
    if command is not None and command.args:  # "/food 650 40" or "/food chicken wrap 650 40"
        await _save_manual(message, session, user, command.args, state)
        return
    text, keyboard = await food_view(session, user)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(FoodCB.filter(F.a.in_({"menu", "day"})))
async def on_menu(callback: CallbackQuery, callback_data: FoodCB, session: AsyncSession,
                  state: FSMContext) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    offset = _offset(callback_data.v) if callback_data.a == "day" else 0
    if offset is None:
        await callback.answer(t("stale_button"))
        return
    await state.clear()
    await callback.answer()
    text, keyboard = await food_view(session, user, offset)
    await send_or_edit(callback, text, keyboard)


@router.callback_query(FoodCB.filter(F.a == "cat"))
async def on_category(callback: CallbackQuery, callback_data: FoodCB, session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    if callback_data.v not in CATEGORIES:
        await callback.answer(t("stale_button"))
        return
    items = foods.foods_for(user.profile.diet, callback_data.v)
    lines = [t("food_cat_header", category=t(f"food_cat_{callback_data.v}")), ""]
    lines += [t("food_list_line", name=html.escape(f.name), serving=html.escape(f.serving),
                kcal=f.kcal, protein=f"{f.protein_g:g}") for f in items]
    if not items:
        lines.append(t("food_cat_empty"))
    await callback.answer()
    await send_or_edit(callback, "\n".join(lines), category_keyboard(items))


@router.callback_query(FoodCB.filter(F.a == "add"))
async def on_add(callback: CallbackQuery, callback_data: FoodCB, session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    food = foods.get_food(callback_data.v)
    if food is None or not foods.allowed(food, user.profile.diet):
        await callback.answer(t("stale_button"))
        return
    entry = await meals.log_food(session, user, food)
    logger.info("Food logged")
    await callback.answer(t("set_logged"))
    text, keyboard = await _logged_view(session, user, entry)
    await send_or_edit(callback, text, keyboard)


@router.callback_query(FoodCB.filter(F.a.in_({"serv", "undo", "del"})))
async def on_entry_action(callback: CallbackQuery, callback_data: FoodCB,
                          session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    raw_id, _, raw_servings = callback_data.v.partition("|")
    entry = await meals.get_entry(session, user, int(raw_id)) if raw_id.isdigit() else None
    if entry is None:
        await callback.answer(t("food_entry_gone"))
        return

    if callback_data.a == "serv":
        try:
            await meals.set_servings(session, entry, float(raw_servings))
        except (ValidationError, ValueError):
            await callback.answer(t("stale_button"))
            return
        await callback.answer()
        text, keyboard = await _logged_view(session, user, entry)
        await send_or_edit(callback, text, keyboard)
        return

    today = await meals.local_today(session, user)
    offset = (entry.day - today).days
    name = entry.name
    await meals.delete_entry(session, entry)
    await callback.answer(t("food_removed", name=name))
    if callback_data.a == "undo":
        text, keyboard = await food_view(session, user)
    else:
        text, keyboard = await _edit_view(session, user, offset)
    await send_or_edit(callback, text, keyboard)


async def _edit_view(session: AsyncSession, user: User, offset: int):
    day = await meals.local_today(session, user) + timedelta(days=offset)
    summary = await meals.day_summary(session, user, day)
    text = t("food_edit_header") if summary.entries else t("food_edit_empty")
    return text, edit_keyboard(summary.entries, offset)


@router.callback_query(FoodCB.filter(F.a == "edit"))
async def on_edit(callback: CallbackQuery, callback_data: FoodCB, session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    offset = _offset(callback_data.v)
    if offset is None:
        await callback.answer(t("stale_button"))
        return
    await callback.answer()
    text, keyboard = await _edit_view(session, user, offset)
    await send_or_edit(callback, text, keyboard)


# ---------- Manual entry ----------

@router.callback_query(FoodCB.filter(F.a == "manual"))
async def on_manual(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if await _user(callback, session) is None:
        return
    await state.set_state(FoodForm.manual)
    await callback.answer()
    await send_or_edit(callback, t("food_manual_prompt"), back_keyboard())


async def _save_manual(message: Message, session: AsyncSession, user: User, text: str,
                       state: FSMContext) -> None:
    try:
        name, kcal, protein = meals.parse_manual(text)
        entry = await meals.log_manual(session, user, name, kcal, protein)
    except ValidationError as error:
        await message.answer(t(error.text_key))
        return
    await state.clear()
    logger.info("Manual food entry logged")
    view, keyboard = await _logged_view(session, user, entry)
    await message.answer(view, reply_markup=keyboard)


@router.message(FoodForm.manual, F.text)
async def on_manual_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(message, session)
    if user is not None:
        await _save_manual(message, session, user, message.text, state)


# ---------- Evening summary (called by the reminder scheduler) ----------

async def send_daily_summary(bot: Bot, session: AsyncSession, user: User) -> bool:
    """Send today's summary if anything was logged. Returns True if sent."""
    today = await meals.local_today(session, user)
    summary = await meals.day_summary(session, user, today)
    if not summary.entries:
        return False  # nothing logged: don't nag
    lines = summary_lines(summary, t("food_today"), user.profile.diet)
    hints = hint_lines(summary, user.profile.diet, evening=True)
    if not hints and summary.kcal_left <= summary.targets.calories * 0.15 \
            and summary.protein_left <= 0:
        hints.append(t("food_hint_great"))
    text = "\n".join([t("food_evening_header")] + lines + ([""] + hints if hints else []))
    await bot.send_message(user.telegram_id, text, reply_markup=back_keyboard())
    return True
