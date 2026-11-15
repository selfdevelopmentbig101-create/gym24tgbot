"""
Exercise cards: one message per exercise with its animation (or image),
details, form tips and buttons (Next, Substitute, Log set).

The same card is used when browsing the library ("lib") and when going
through a plan day ("day"). Tapping Next/Substitute edits the card in place.
"""
import asyncio
import html
import logging
from dataclasses import dataclass

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InputMediaAnimation,
    InputMediaPhoto,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, MediaCache, PlanExercise
from keyboards.exercises import CardCB, card_keyboard
from services import exercises as exercise_service
from services import plans, users
from services.exercise_media import build_media
from utils.texts import label, t

logger = logging.getLogger(__name__)
router = Router(name="cards")

MAX_TIPS_LENGTH = 600  # Telegram captions are limited to 1024 characters


@dataclass
class Card:
    exercise: Exercise
    ctx: str               # "lib" or "day"
    ref: str               # muscle group or plan entry id
    position: int          # 1-based
    total: int
    day_label: str = ""
    entry: PlanExercise | None = None


# ---------- Text helpers ----------

def format_reps(entry: PlanExercise) -> str:
    key = "seconds_range" if entry.timed else "reps_range"
    return t(key, low=entry.rep_min, high=entry.rep_max)


def format_rest(seconds: int) -> str:
    if seconds >= 120 and seconds % 30 == 0:
        return t("rest_minutes", minutes=f"{seconds / 60:g}")
    return t("rest_seconds", seconds=seconds)


def day_label(name_key: str, suffix: str) -> str:
    """"Upper A", "Day 2", or a name the user typed ("~Arms" -> "Arms", HTML-escaped)."""
    if name_key.startswith("~"):
        return html.escape(name_key[1:])
    return f"{t('day_' + name_key)} {suffix}".strip()


def card_caption(card: Card) -> str:
    ex = card.exercise
    lines = [
        f"<b>{html.escape(ex.name)}</b>",
        f"🎯 {label('muscle', ex.muscle_group)} · {label('move', ex.movement_type)}",
        f"🛠 {label('gear', ex.equipment)} · {label('level', ex.difficulty)}",
        "",
    ]
    if card.entry is not None:
        lines.append(t("card_plan_position", day=card.day_label, pos=card.position, total=card.total))
        lines.append(t("card_prescription", sets=card.entry.sets, reps=format_reps(card.entry),
                       rest=format_rest(card.entry.rest_seconds)))
    else:
        lines.append(t("card_library_position", pos=card.position, total=card.total))
    lines.append("")

    tips = (ex.form_tips or "").strip()
    if tips:
        if len(tips) > MAX_TIPS_LENGTH:
            tips = tips[:MAX_TIPS_LENGTH].rsplit(" ", 1)[0] + "…"
        lines.append(t("card_form_tips", tips=html.escape(tips)))
    else:
        lines.append(t("card_form_tips_missing"))
    return "\n".join(lines)


# ---------- Media ----------

async def _media_for(session: AsyncSession, exercise_id: str):
    """(kind, file to send, cache key) or None when the exercise has no images."""
    media = await asyncio.to_thread(build_media, exercise_id)  # Pillow work off the event loop
    if media is None:
        return None
    cached = await session.get(MediaCache, media.cache_key)
    return media.kind, (cached.file_id if cached else FSInputFile(media.path)), media.cache_key


async def _remember_file_id(session: AsyncSession, cache_key: str, message: Message | bool) -> None:
    """Save Telegram's file_id so next time we send the file without uploading it."""
    if not isinstance(message, Message):
        return
    file = message.animation or message.document or (message.photo[-1] if message.photo else None)
    if file is None:
        return
    cached = await session.get(MediaCache, cache_key)
    if cached is None:
        session.add(MediaCache(key=cache_key, file_id=file.file_id))
    else:
        cached.file_id = file.file_id
    await session.commit()


async def _forget_file_id(session: AsyncSession, cache_key: str) -> None:
    cached = await session.get(MediaCache, cache_key)
    if cached:
        await session.delete(cached)
        await session.commit()


def _has_media(message: Message) -> bool:
    return bool(message.animation or message.photo or message.document)


async def _send_new(target: Message, session: AsyncSession, card: Card, caption: str,
                    keyboard: InlineKeyboardMarkup) -> None:
    media = await _media_for(session, card.exercise.id)
    if media is None:
        await target.answer(caption, reply_markup=keyboard)
        return
    kind, file, key = media
    try:
        if kind == "animation":
            sent = await target.answer_animation(file, caption=caption, reply_markup=keyboard)
        else:
            sent = await target.answer_photo(file, caption=caption, reply_markup=keyboard)
    except TelegramBadRequest:
        if isinstance(file, str):  # a stale cached file_id: upload again once
            await _forget_file_id(session, key)
            return await _send_new(target, session, card, caption, keyboard)
        raise
    await _remember_file_id(session, key, sent)


async def show_card(event: Message | CallbackQuery, session: AsyncSession, card: Card) -> None:
    """Send a card, or update the card the user tapped a button on."""
    caption = card_caption(card)
    keyboard = card_keyboard(card.ctx, card.ref, card.exercise.id)

    if isinstance(event, Message):
        await _send_new(event, session, card, caption, keyboard)
        return

    message = event.message
    media = await _media_for(session, card.exercise.id)
    try:
        if media and _has_media(message):
            kind, file, key = media
            input_media = (InputMediaAnimation if kind == "animation" else InputMediaPhoto)(
                media=file, caption=caption)
            edited = await message.edit_media(input_media, reply_markup=keyboard)
            await _remember_file_id(session, key, edited)
            return
        if media is None and not _has_media(message):
            await message.edit_text(caption, reply_markup=keyboard)
            return
    except TelegramBadRequest as error:
        if "not modified" in str(error):
            return
        logger.warning("Could not edit card, sending a new one: %s", error)
        if media and isinstance(media[1], str):
            await _forget_file_id(session, media[2])

    # Text <-> media can't be swapped by editing: replace the message.
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    await _send_new(message, session, card, caption, keyboard)


# ---------- Building cards ----------

async def library_card(session: AsyncSession, profile, group: str,
                       exercise_id: str | None = None) -> Card | None:
    """Card for an exercise in a muscle group (the first one if exercise_id is None)."""
    items = await exercise_service.library_exercises(session, group, profile)
    if not items:
        return None
    ids = [ex.id for ex in items]
    index = ids.index(exercise_id) if exercise_id in ids else 0
    return Card(items[index], "lib", group, index + 1, len(items))


async def plan_card(session: AsyncSession, entry: PlanExercise) -> Card:
    day = entry.day
    entries = day.exercises
    position = next(i for i, e in enumerate(entries) if e.id == entry.id) + 1
    return Card(entry.exercise, "day", str(entry.id), position, len(entries),
                day_label=day_label(day.name_key, day.suffix), entry=entry)


# ---------- Button handlers ----------

@router.callback_query(CardCB.filter())
async def on_card_button(callback: CallbackQuery, callback_data: CardCB, bot: Bot,
                         session: AsyncSession) -> None:
    if callback_data.action == "log":
        await _log_button(callback, callback_data, bot, session)
        return
    if callback_data.ctx == "day":
        await _day_button(callback, callback_data, session)
    else:
        await _library_button(callback, callback_data, session)


async def _log_button(callback: CallbackQuery, data: CardCB, bot: Bot,
                      session: AsyncSession) -> None:
    """'Log set' on an exercise card: open the workout logger at this exercise."""
    from handlers.workout import open_logger_for  # here to avoid a circular import

    user = await users.get_user(session, callback.from_user.id)
    if user is None or user.profile is None:
        await callback.answer(t("need_profile"), show_alert=True)
        return
    exercise = await exercise_service.get_exercise(session, data.ex)
    day_index = None
    if data.ctx == "day" and data.ref.isdigit():
        entry = await plans.get_plan_exercise(session, user, int(data.ref))
        if entry is None:
            await callback.answer(t("plan_changed"), show_alert=True)
            return
        day_index = entry.day.day_index
    if exercise is None:
        await callback.answer(t("stale_button"))
        return
    await callback.answer()
    if not await open_logger_for(callback.message, bot, session, user, exercise, day_index):
        await callback.message.answer(t("start_workout_first"))


async def _library_button(callback: CallbackQuery, data: CardCB, session: AsyncSession) -> None:
    user = await users.get_user(session, callback.from_user.id)
    profile = user.profile if user else None
    items = await exercise_service.library_exercises(session, data.ref, profile)
    if not items:
        await callback.answer(t("library_empty"))
        return
    ids = [ex.id for ex in items]

    if data.action == "next":
        index = (ids.index(data.ex) + 1) % len(ids) if data.ex in ids else 0
        await callback.answer()
        await show_card(callback, session, Card(items[index], "lib", data.ref, index + 1, len(items)))
        return

    # Substitute
    catalog = await exercise_service.load_catalog(session)
    current = catalog.get(data.ex)
    if current is None:
        await callback.answer(t("stale_button"))
        return
    if profile is not None:
        substitute = exercise_service.pick_substitute(
            current, catalog, exercise_service.UserFilter.from_profile(profile))
    else:
        substitute = next((catalog[s] for s in current.substitute_ids if s in catalog), None)
    if substitute is None:
        await callback.answer(t("no_substitute"), show_alert=True)
        return
    card = await library_card(session, profile, substitute.muscle_group, substitute.id)
    if card is None or card.exercise.id != substitute.id:
        # Substitute isn't in the filtered group list (only happens without a profile).
        card = Card(substitute, "lib", substitute.muscle_group, 1, 1)
    await callback.answer()
    await show_card(callback, session, card)


async def _day_button(callback: CallbackQuery, data: CardCB, session: AsyncSession) -> None:
    user = await users.get_user(session, callback.from_user.id)
    entry = None
    if user is not None and user.profile is not None and data.ref.isdigit():
        entry = await plans.get_plan_exercise(session, user, int(data.ref))
    if entry is None:
        await callback.answer(t("plan_changed"), show_alert=True)
        return

    if data.action == "next":
        entries = entry.day.exercises
        index = next(i for i, e in enumerate(entries) if e.id == entry.id)
        await callback.answer()
        await show_card(callback, session, await plan_card(session, entries[(index + 1) % len(entries)]))
        return

    # Substitute: swap the exercise in the user's plan.
    if entry.exercise_id != data.ex:
        await callback.answer(t("stale_button"))
        return
    updated = await plans.substitute_in_plan(session, user, entry)
    if updated is None:
        await callback.answer(t("no_substitute"), show_alert=True)
        return
    await callback.answer(t("substituted"))
    await show_card(callback, session, await plan_card(session, updated))
