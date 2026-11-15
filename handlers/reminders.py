"""
/reminders and the reminder messages themselves.

- Setup is 1 tap: pick the button showing your current time (sets the time
  zone), and sensible defaults are applied (training days from your plan).
- make_notifier() builds the function the scheduler calls. It checks the
  database before sending, so nobody gets a "workout day!" message after
  they've already trained.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import ReminderSettings, User
from handlers.cards import day_label
from handlers.onboarding import send_or_edit
from keyboards.menu import MenuButton
from keyboards.progress import (
    RemCB,
    days_keyboard,
    nudge_keyboard,
    reminders_keyboard,
    time_keyboard,
    timezone_keyboard,
    weight_keyboard,
)
from keyboards.workout import WorkoutCB
from services import body, plans, reminders, users, workouts
from services.reminders import DEFAULT_WORKOUT_DAYS, REMINDER_HOURS, offset_name
from services.scheduler import sync_user
from utils.texts import set_language, t

logger = logging.getLogger(__name__)
router = Router(name="reminders")


class ReminderForm(StatesGroup):
    timezone = State()  # waiting for a typed time zone name


async def _user(event, session: AsyncSession) -> User | None:
    user = await users.get_user(session, event.from_user.id)
    if user is None or user.profile is None:
        if isinstance(event, CallbackQuery):
            await event.answer()
        await send_or_edit(event, t("need_profile"))
        return None
    return user


def reminders_text(settings: ReminderSettings) -> str:
    off = t("reminders_off_short")
    days = ", ".join(t(f"weekday_{d}") for d in sorted(settings.workout_days or []))
    workout = (t("reminders_workout_on", days=days, time=settings.workout_time)
               if settings.workout_enabled and days else off)
    if settings.weighin_mode == "daily":
        weighin = t("reminders_weighin_daily", time=settings.weighin_time)
    elif settings.weighin_mode == "weekly":
        weighin = t("reminders_weighin_weekly", day=t(f"weekday_{settings.weighin_day}"),
                    time=settings.weighin_time)
    else:
        weighin = off
    nudge = (t("reminders_nudge_on", time=settings.nudge_time)
             if settings.nudge_enabled and settings.workout_enabled else off)
    summary = t("reminders_summary_on", time=settings.summary_time) if settings.summary_enabled else off
    text = t("reminders_view", workout=workout, weighin=weighin, nudge=nudge, summary=summary,
             tz=settings.timezone, now=reminders.local_now(settings).strftime("%H:%M"))
    if settings.timezone.startswith("UTC") and settings.timezone != "UTC":
        text += "\n" + t("reminders_tz_fixed_note")
    return text


async def _show(event, settings: ReminderSettings) -> None:
    await send_or_edit(event, reminders_text(settings), reminders_keyboard(settings))


@router.message(Command("reminders"))
@router.message(MenuButton("menu_reminders"))
async def cmd_reminders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(message, session)
    if user is None:
        return
    settings = await reminders.get_settings(session, user)
    if settings is None:
        await state.set_state(ReminderForm.timezone)
        await message.answer(t("reminders_off"), reply_markup=timezone_keyboard())
        return
    await state.clear()
    await _show(message, settings)


async def _apply_timezone(event, session: AsyncSession, user: User, tz_name: str) -> None:
    settings = await reminders.enable(session, user, tz_name)
    sync_user(user.id, settings)
    await _show(event, settings)


@router.message(ReminderForm.timezone, F.text)
async def on_typed_timezone(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(message, session)
    if user is None:
        return
    name = message.text.strip()
    if not reminders.is_valid_tz(name):
        await message.answer(t("rem_tz_invalid"))
        return
    await state.clear()
    await _apply_timezone(message, session, user, name)


@router.callback_query(RemCB.filter(F.a.in_({"resched", "skip", "fewer"})))
async def on_nudge_answer(callback: CallbackQuery, callback_data: RemCB, session: AsyncSession) -> None:
    """Buttons under the missed-workout nudge."""
    user = await _user(callback, session)
    if user is None:
        return
    settings = await reminders.get_settings(session, user)
    if settings is None:
        await callback.answer(t("stale_button"))
        return
    await callback.answer()

    if callback_data.a == "resched":
        when = await reminders.reschedule(session, settings, 2 if callback_data.v == "2" else 1)
        sync_user(user.id, settings)
        await send_or_edit(callback, t("resched_done", day=t(f"weekday_{when.weekday()}"),
                                       time=when.strftime("%H:%M")))
    elif callback_data.a == "skip":
        await send_or_edit(callback, t("resched_skipped"))
    else:
        days = int(callback_data.v) if callback_data.v.isdigit() else 0
        if not 2 <= days < user.profile.training_days:
            await send_or_edit(callback, t("stale_button"))
            return
        await users.update_profile_field(session, user, "training_days", days)
        await plans.generate_for_user(session, user)
        settings.workout_days = DEFAULT_WORKOUT_DAYS[days]
        settings.missed_streak = 0
        await session.commit()
        sync_user(user.id, settings)
        await send_or_edit(callback, t("fewer_days_done", n=days))


@router.callback_query(RemCB.filter())
async def on_reminder_settings(callback: CallbackQuery, callback_data: RemCB,
                               session: AsyncSession, state: FSMContext) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    action, value = callback_data.a, callback_data.v

    if action == "tz":
        minutes = int(value) if value.lstrip("-").isdigit() else None
        if minutes not in reminders.OFFSETS_MINUTES:
            await callback.answer(t("stale_button"))
            return
        await state.clear()
        await callback.answer()
        await _apply_timezone(callback, session, user, offset_name(minutes))
        return

    settings = await reminders.get_settings(session, user)
    if settings is None:
        await callback.answer(t("stale_button"))
        return

    if action == "tzpick":
        await state.set_state(ReminderForm.timezone)
        await callback.answer()
        await send_or_edit(callback, t("reminders_tz_pick"), timezone_keyboard())
        return
    if action == "alloff":
        await reminders.disable(session, user)
        sync_user(user.id, None)
        await callback.answer()
        await send_or_edit(callback, t("rem_all_off_done"))
        return
    if action == "time":
        await callback.answer()
        await send_or_edit(callback, t("rem_pick_time"), time_keyboard(value))
        return
    if action == "days":
        await callback.answer()
        await send_or_edit(callback, t("rem_pick_days"), days_keyboard(settings.workout_days or []))
        return
    if action == "day":
        day = int(value) if value.isdigit() else -1
        if 0 <= day <= 6:
            days = set(settings.workout_days or [])
            days ^= {day}  # toggle
            settings.workout_days = sorted(days)
            await session.commit()
            sync_user(user.id, settings)
        await callback.answer()
        try:
            await callback.message.edit_reply_markup(reply_markup=days_keyboard(settings.workout_days))
        except TelegramBadRequest:
            pass
        return

    if action == "wtoggle":
        settings.workout_enabled = not settings.workout_enabled
    elif action == "stoggle":
        settings.summary_enabled = not settings.summary_enabled
    elif action == "ntoggle":
        settings.nudge_enabled = not settings.nudge_enabled
    elif action == "wimode":
        modes = ["off", "daily", "weekly"]
        settings.weighin_mode = modes[(modes.index(settings.weighin_mode) + 1) % 3]
    elif action == "widay":
        settings.weighin_day = (settings.weighin_day + 1) % 7
    elif action == "settime":
        field, _, raw = value.partition("|")
        hhmm = f"{raw[:2]}:{raw[2:]}"
        valid_times = {f"{h:02d}:00" for h in REMINDER_HOURS}
        if field in ("workout", "weighin", "nudge", "summary") and hhmm in valid_times:
            setattr(settings, f"{field}_time", hhmm)
    # "view" just redraws.
    await session.commit()
    sync_user(user.id, settings)
    await callback.answer()
    await _show(callback, settings)


# ---------- Sending reminders ----------

def make_notifier(bot: Bot, session_factory: async_sessionmaker):
    """The function the scheduler calls with (kind, internal user id)."""

    async def notify(kind: str, user_id: int) -> None:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            settings = await session.get(ReminderSettings, user_id)
            if user is None or user.profile is None or settings is None:
                return
            set_language(user.language)  # runs outside an update, so set it here
            today = reminders.local_now(settings).date()
            try:
                if kind in ("workout", "resched"):
                    await _workout_reminder(bot, session, user, settings, today, kind)
                elif kind == "weighin":
                    if not await reminders.weighed_on(session, user, settings, today):
                        start = await body.last_weight(session, user) or user.profile.weight_kg
                        await bot.send_message(user.telegram_id, t("remind_weighin"),
                                               reply_markup=weight_keyboard(start))
                elif kind == "summary":
                    from handlers.food import send_daily_summary  # avoid a circular import
                    await send_daily_summary(bot, session, user)
                elif kind == "nudge":
                    await _nudge(bot, session, user, settings, today)
            except TelegramForbiddenError:
                logger.info("User blocked the bot; reminder skipped")

    return notify


async def _workout_reminder(bot: Bot, session: AsyncSession, user: User,
                            settings: ReminderSettings, today, kind: str) -> None:
    if kind == "resched":
        settings.rescheduled_for = None
        await session.commit()
    if await reminders.trained_on(session, user, settings, today):
        return
    plan = await plans.get_plan(session, user)
    if plan is None or not plan.days:
        return
    index = await workouts.next_day_index(session, user, plan)
    day = plan.days[index]
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=t("btn_start_workout"), callback_data=WorkoutCB(a="overview"))
    await bot.send_message(user.telegram_id,
                           t("remind_workout", n=index + 1, name=day_label(day.name_key, day.suffix)),
                           reply_markup=keyboard.as_markup())


async def _nudge(bot: Bot, session: AsyncSession, user: User,
                 settings: ReminderSettings, today) -> None:
    if await reminders.trained_on(session, user, settings, today):
        return
    settings.missed_streak += 1
    await session.commit()
    text = t("remind_nudge")
    fewer = None
    # Missing a lot? Offer a lighter schedule instead of guilt.
    if settings.missed_streak >= 3 and user.profile.training_days > 2:
        fewer = user.profile.training_days - 1
        text += "\n\n" + t("remind_nudge_streak", n=settings.missed_streak)
    await bot.send_message(user.telegram_id, text,
                           reply_markup=nudge_keyboard(settings.workout_time, fewer))


