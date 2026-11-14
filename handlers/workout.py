"""
/workout: start today's workout and log sets with buttons.

One "logger card" message shows the current exercise: target, last time's
numbers, an overload hint, today's sets and a pre-filled Log button.
- Log the suggested set: 1 tap. Adjust weight or reps first: 2 taps.
- After each set a rest timer starts; when it ends you get a new message
  (so your phone notifies you) with a button to log the next set.
"""
import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import Exercise, User, WorkoutPlan, WorkoutSession
from handlers.cards import day_label, format_rest
from handlers.onboarding import send_or_edit
from keyboards.workout import (
    WorkoutCB,
    card_keyboard,
    exercise_list_keyboard,
    overview_keyboard,
    rest_over_keyboard,
)
from handlers import extras
from services import achievements, plans, reminders, users, workouts
from services.progression import Suggestion
from services.rest_timer import rest_timers
from services.scheduler import sync_user
from utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="workout")

# "62.5x8", "62.5 x 8", "62,5*8", "62.5 8", "60kg x 10" -> weight and reps; "8" -> reps only.
SET_WITH_WEIGHT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:kg)?\s*(?:[x×*]|\s)\s*(\d+)\s*$", re.I)
REPS_ONLY = re.compile(r"^\s*(\d+)\s*(?:reps?|s)?\s*$", re.I)


# ---------- Formatting ----------

def fmt_weight(weight: float, equipment: str) -> str:
    if equipment == "bodyweight":
        return "BW" if weight == 0 else f"BW+{weight:g} kg"
    return f"{weight:g} kg"


def fmt_set(weight: float, reps: int, equipment: str, timed: bool) -> str:
    if timed:
        return t("unit_seconds", n=reps)
    return f"{fmt_weight(weight, equipment)} × {reps}"


def fmt_sets(sets, equipment: str, timed: bool) -> str:
    return " · ".join(fmt_set(s.weight_kg, s.reps, equipment, timed) for s in sets)


def fmt_reps_range(item: dict) -> str:
    key = "seconds_range" if item["timed"] else "reps_range"
    return t(key, low=item["rep_min"], high=item["rep_max"])


def hint_params(hint: Suggestion, exercise: Exercise, timed: bool) -> dict:
    """Fill units into the suggestion's values, e.g. weight 62.5 -> '62.5 kg', reps 8 -> '8 reps'."""
    params = dict(hint.params)
    if "weight" in params:
        params["weight"] = fmt_weight(params["weight"], exercise.equipment)
    if "reps" in params:
        params["reps"] = t("unit_seconds" if timed else "unit_reps", n=params["reps"])
    return params


def fmt_time(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


# ---------- Views ----------

async def overview_view(session: AsyncSession, user: User, plan: WorkoutPlan, day_index: int):
    day = plan.days[day_index]
    lines = [t("workout_overview", n=day_index + 1, name=day_label(day.name_key, day.suffix)), ""]
    for entry in day.exercises:
        item = {"timed": entry.timed, "rep_min": entry.rep_min, "rep_max": entry.rep_max}
        lines.append(t("workout_line", name=html.escape(entry.exercise.name), sets=entry.sets,
                       reps=fmt_reps_range(item)))
        past = await workouts.history(session, user, entry.exercise_id, limit=1)
        if past:
            lines.append(t("workout_line_last",
                           last=fmt_sets(past[0], entry.exercise.equipment, entry.timed)))
    lines += ["", t("workout_overview_footer")]
    labels = [day_label(d.name_key, d.suffix) for d in plan.days]
    return "\n".join(lines), overview_keyboard(day_index, labels)


async def card_view(session: AsyncSession, user: User, ws: WorkoutSession):
    index = ws.current_index
    item = ws.items[index]
    timed = item["timed"]
    exercise = await session.get(Exercise, item["exercise_id"])
    today = workouts.sets_for(ws, exercise.id)
    hint, previous = await workouts.suggestion_for(session, user, ws, index)

    lines = [
        t("workout_card_header", day=day_label(ws.name_key, ws.suffix) or "Workout",
          pos=index + 1, total=len(ws.items)),
        f"<b>{html.escape(exercise.name)}</b>",
        t("workout_target", sets=item["sets"], reps=fmt_reps_range(item),
          rest=format_rest(item["rest_seconds"])),
    ]
    if await workouts.in_deload(session, user):
        lines.insert(1, t("deload_banner", until=user.profile.deload_until.strftime("%d %b")))
    if previous:
        lines.append(t("workout_last_time", sets=fmt_sets(previous, exercise.equipment, timed)))
        lines.append(t(f"hint_{hint.kind}", **hint_params(hint, exercise, timed)))
    else:
        lines.append(t("workout_first_time", low=item["rep_min"], high=item["rep_max"]))

    if today:
        lines += ["", t("workout_today")]
        lines += [t("workout_set_line", n=s.set_number, set=fmt_set(s.weight_kg, s.reps,
                                                                       exercise.equipment, timed))
                  + (" 🏆" if s.pr else "")
                  for s in today]
    lines.append("")
    done = len(today)
    if done < item["sets"]:
        lines.append(t("workout_next_set", n=done + 1, total=item["sets"]))
    else:
        lines.append(t("workout_exercise_done"))
        lines.append(t("workout_extra_set", n=done + 1, total=item["sets"]))

    remaining = rest_timers.remaining(user.telegram_id)
    if remaining:
        lines.append(t("workout_resting", time=fmt_time(remaining)))
    lines.append(t("workout_type_hint"))

    same = await workouts.same_as_last_time(session, user, ws)
    keyboard = card_keyboard(
        ws.id, timed=timed,
        log_label=t("btn_log", set=fmt_set(ws.draft_weight, ws.draft_reps, exercise.equipment, timed)),
        same_label=t("btn_same_as_last", set=fmt_set(same.weight_kg, same.reps, exercise.equipment, timed))
        if same else None,
    )
    return "\n".join(lines), keyboard


async def list_view(session: AsyncSession, ws: WorkoutSession):
    labels = []
    for index, item in enumerate(ws.items):
        exercise = await session.get(Exercise, item["exercise_id"])
        mark = "✅" if workouts.item_done(ws, index) else ("▶️" if index == ws.current_index else "▫️")
        labels.append(f"{mark} {exercise.name}")
    return t("workout_list"), exercise_list_keyboard(ws.id, labels)


def summary_text(summary: workouts.WorkoutSummary, plan: WorkoutPlan | None, day_index) -> str:
    parts = [t("workout_done", day=day_label(summary.name_key, summary.suffix) or "Workout",
               minutes=summary.minutes, sets=summary.total_sets, volume=f"{summary.volume_kg:,.0f}")]
    lines, hints = [], []
    for ex in summary.exercises:
        timed = ex.timed
        lines.append(t("workout_done_line", name=html.escape(ex.exercise.name),
                       sets=fmt_sets(ex.sets, ex.exercise.equipment, timed)))
        if ex.next_time is not None and ex.next_time.kind != "first":
            hints.append(t(f"next_{ex.next_time.kind}", name=html.escape(ex.exercise.name),
                           **hint_params(ex.next_time, ex.exercise, timed)))
    parts.append("\n".join(lines))
    prs = [ex.exercise.name for ex in summary.exercises if any(s.pr for s in ex.sets)]
    if prs:
        parts.append(t("workout_prs", names=html.escape(", ".join(prs))))
    if hints:
        parts.append(t("workout_next_time") + "\n" + "\n".join(hints))
    if plan is not None and plan.days and day_index is not None:
        nxt = (day_index + 1) % len(plan.days)
        day = plan.days[nxt]
        parts.append(t("workout_next_day", n=nxt + 1, name=day_label(day.name_key, day.suffix)))
    return "\n\n".join(parts)


# ---------- Sending the card ----------

async def send_new_card(target: Message, bot: Bot, session: AsyncSession, user: User,
                        ws: WorkoutSession) -> None:
    """Send the card as a new message at the bottom of the chat (and remove the old one)."""
    text, keyboard = await card_view(session, user, ws)
    old_id = ws.card_message_id
    sent = await target.answer(text, reply_markup=keyboard)
    ws.card_message_id = sent.message_id
    await session.commit()
    if old_id and old_id != sent.message_id:
        try:
            await bot.delete_message(chat_id=target.chat.id, message_id=old_id)
        except TelegramBadRequest:
            pass  # already gone or too old


async def update_card(callback: CallbackQuery, bot: Bot, session: AsyncSession, user: User,
                      ws: WorkoutSession, text: str | None = None, keyboard=None) -> None:
    """
    Show the card in the message that was tapped. If that wasn't the card
    (e.g. the rest-over notification), it becomes the card and the old card is removed.
    """
    if text is None:
        text, keyboard = await card_view(session, user, ws)
    message = callback.message
    try:
        await message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as error:
        if "not modified" not in str(error):
            raise
    if ws.card_message_id != message.message_id:
        old_id, ws.card_message_id = ws.card_message_id, message.message_id
        await session.commit()
        if old_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=old_id)
            except TelegramBadRequest:
                pass


# ---------- Rest timer ----------

def start_rest_timer(bot: Bot, session_factory: async_sessionmaker, user: User,
                     ws: WorkoutSession) -> None:
    if workouts.all_done(ws):
        return
    seconds = ws.items[ws.current_index]["rest_seconds"]
    telegram_id, session_id = user.telegram_id, ws.id

    async def rest_over() -> None:
        async with session_factory() as session:
            owner = await users.get_user(session, telegram_id)
            current = await workouts.get_session(session, owner, session_id) if owner else None
            if current is None or current.finished_at is not None:
                return
            item = current.items[current.current_index]
            exercise = await session.get(Exercise, item["exercise_id"])
            done = len(workouts.sets_for(current, exercise.id))
            if done < item["sets"]:
                set_text = fmt_set(current.draft_weight, current.draft_reps, exercise.equipment,
                                   item["timed"])
                text = t("rest_over", name=html.escape(exercise.name), n=done + 1, set=set_text)
                keyboard = rest_over_keyboard(session_id, t("btn_log", set=set_text), "log")
            else:
                nxt = current.items[(current.current_index + 1) % len(current.items)]
                nxt_ex = await session.get(Exercise, nxt["exercise_id"])
                text = t("rest_over_next", name=html.escape(nxt_ex.name))
                keyboard = rest_over_keyboard(session_id, t("btn_next_exercise"), "next")
            await bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)

    rest_timers.start(telegram_id, seconds, rest_over)


# ---------- Commands ----------

async def _user_with_profile(event, session: AsyncSession) -> User | None:
    user = await users.get_user(session, event.from_user.id)
    if user is None or user.profile is None:
        if isinstance(event, CallbackQuery):
            await event.answer()
        await send_or_edit(event, t("need_profile"))
        return None
    return user


@router.message(Command("workout"))
async def cmd_workout(message: Message, bot: Bot, session: AsyncSession) -> None:
    user = await _user_with_profile(message, session)
    if user is None:
        return
    ws = await workouts.get_active(session, user)
    if ws is not None:
        await send_new_card(message, bot, session, user, ws)
        return
    plan = await plans.get_or_create_plan(session, user)
    if plan is None or not plan.days:
        await message.answer(t("plan_empty"))
        return
    day_index = await workouts.next_day_index(session, user, plan)
    text, keyboard = await overview_view(session, user, plan, day_index)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(WorkoutCB.filter(F.a.in_({"overview", "day", "start"})))
async def on_overview(callback: CallbackQuery, callback_data: WorkoutCB, bot: Bot,
                      session: AsyncSession) -> None:
    user = await _user_with_profile(callback, session)
    if user is None:
        return
    plan = await plans.get_or_create_plan(session, user)
    if plan is None or not plan.days:
        await callback.answer(t("plan_empty"), show_alert=True)
        return

    if callback_data.a == "overview":
        ws = await workouts.get_active(session, user)
        await callback.answer()
        if ws is not None:
            await send_new_card(callback.message, bot, session, user, ws)
            return
        day_index = await workouts.next_day_index(session, user, plan)
    else:
        day_index = int(callback_data.v) if callback_data.v.isdigit() else -1
        if not 0 <= day_index < len(plan.days) or not plan.days[day_index].exercises:
            await callback.answer(t("plan_changed"), show_alert=True)
            return
        await callback.answer()

    if callback_data.a == "start":
        ws = await workouts.start(session, user, plan, day_index)
        await update_card(callback, bot, session, user, ws)
        return
    text, keyboard = await overview_view(session, user, plan, day_index)
    await send_or_edit(callback, text, keyboard)


# ---------- Logger card buttons ----------

@router.callback_query(WorkoutCB.filter())
async def on_card_action(callback: CallbackQuery, callback_data: WorkoutCB, bot: Bot,
                         session: AsyncSession, session_factory: async_sessionmaker) -> None:
    user = await _user_with_profile(callback, session)
    if user is None:
        return
    ws = await workouts.get_session(session, user, callback_data.s)
    if ws is None or ws.finished_at is not None:
        await callback.answer(t("workout_ended"), show_alert=True)
        return

    action, value = callback_data.a, callback_data.v
    exercise = await session.get(Exercise, ws.items[ws.current_index]["exercise_id"])
    timed = ws.items[ws.current_index]["timed"]
    popup = None

    try:
        if action == "w":
            await workouts.adjust_draft(session, ws, weight_delta=float(value))
        elif action == "r":
            await workouts.adjust_draft(session, ws, reps_delta=int(value))
        elif action in ("log", "same"):
            weight = reps = None
            if action == "same":
                last = await workouts.same_as_last_time(session, user, ws)
                if last is None:
                    await callback.answer(t("stale_button"))
                    return
                weight, reps = last.weight_kg, last.reps
            entry = await workouts.log_set(session, user, ws, weight, reps)
            start_rest_timer(bot, session_factory, user, ws)
            popup = t("set_logged") + " " + fmt_set(entry.weight_kg, entry.reps, exercise.equipment, timed)
            if entry.pr:
                popup = t("new_pr", name=exercise.name, value=f"{entry.estimate:.1f}",
                          previous=f"{entry.previous_best:.1f}")
        elif action == "undo":
            removed = await workouts.undo_last(session, ws)
            if removed is None:
                await callback.answer(t("nothing_to_undo"))
                return
            rest_timers.cancel(user.telegram_id)
            removed_ex = await session.get(Exercise, removed.exercise_id)
            removed_timed = ws.items[ws.current_index]["timed"]
            popup = t("set_undone", set=fmt_set(removed.weight_kg, removed.reps,
                                                removed_ex.equipment, removed_timed))
        elif action == "swap":
            substitute = await workouts.swap_current(session, user, ws)
            if substitute is None:
                await callback.answer(t("no_substitute"), show_alert=True)
                return
            popup = t("swapped", name=substitute.name)
        elif action == "next":
            await workouts.enter_exercise(session, user, ws, ws.current_index + 1)
        elif action == "goto":
            if not value.isdigit() or int(value) >= len(ws.items):
                await callback.answer(t("stale_button"))
                return
            await workouts.enter_exercise(session, user, ws, int(value))
        elif action == "list":
            await callback.answer()
            text, keyboard = await list_view(session, ws)
            await update_card(callback, bot, session, user, ws, text, keyboard)
            return
        elif action == "finish":
            await _finish(callback, session, user, ws)
            return
        # "card" (back from the list) just redraws the card.
    except workouts.LogError as error:
        await callback.answer(t(error.text_key), show_alert=True)
        return

    await callback.answer(popup)
    await update_card(callback, bot, session, user, ws)


async def _finish(callback: CallbackQuery, session: AsyncSession, user: User,
                  ws: WorkoutSession) -> None:
    rest_timers.cancel(user.telegram_id)
    day_index = ws.day_index
    summary = await workouts.finish(session, user, ws)
    await callback.answer()
    if summary is None:
        await send_or_edit(callback, t("workout_discarded"))
        return
    # Missed-workout streak resets and any "remind me tomorrow" is cancelled.
    sync_user(user.id, await reminders.workout_finished(session, user))
    plan = await plans.get_plan(session, user)
    parts = [summary_text(summary, plan, day_index)]
    new = await achievements.check_new(session, user)
    extra = [extras.streak_text(await achievements.compute_stats(session, user)),
             extras.new_achievements_text(new)]
    parts += [p for p in extra if p]
    await send_or_edit(callback, "\n\n".join(parts))
    await extras.send_suggestions(callback.message, session, user, calories=False)


# ---------- Typed sets ----------

@router.message(StateFilter(None), F.text.regexp(SET_WITH_WEIGHT) | F.text.regexp(REPS_ONLY))
async def on_typed_set(message: Message, bot: Bot, session: AsyncSession,
                       session_factory: async_sessionmaker) -> None:
    user = await users.get_user(session, message.from_user.id)
    ws = await workouts.get_active(session, user) if user and user.profile else None
    if ws is None:
        await message.answer(t("no_active_workout"))
        return

    match = SET_WITH_WEIGHT.match(message.text)
    if match:
        weight, reps = float(match.group(1).replace(",", ".")), int(match.group(2))
    else:
        weight, reps = None, int(REPS_ONLY.match(message.text).group(1))
    try:
        await workouts.log_set(session, user, ws, weight, reps)
    except workouts.LogError as error:
        await message.answer(t(error.text_key))
        return
    start_rest_timer(bot, session_factory, user, ws)
    await send_new_card(message, bot, session, user, ws)


# ---------- Entry from exercise cards (Phase 2 "Log set" button) ----------

async def open_logger_for(message: Message, bot: Bot, session: AsyncSession, user: User,
                          exercise: Exercise, plan_day_index: int | None) -> bool:
    """
    Jump to `exercise` in the logger. From a plan day, starts that day's workout
    if needed. Returns False if there's no workout and no plan day to start.
    """
    ws = await workouts.get_active(session, user)
    if ws is None or (plan_day_index is not None and ws.day_index != plan_day_index and not ws.sets):
        if plan_day_index is None:
            return False
        plan = await plans.get_plan(session, user)
        ws = await workouts.start(session, user, plan, plan_day_index)
    index = await workouts.add_exercise(session, user, ws, exercise)
    await workouts.enter_exercise(session, user, ws, index)
    await send_new_card(message, bot, session, user, ws)
    return True


