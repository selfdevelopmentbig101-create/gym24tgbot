"""
/app: open the Telegram Mini App (full-screen workout logger and charts).
The finished workout comes back as a web_app_data message.
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from handlers import extras
from handlers.cards import day_label
from handlers.workout import summary_text
from keyboards.menu import main_menu_keyboard
from services import achievements, plans, reminders, users, webapp, workouts
from services.scheduler import sync_user
from utils.texts import current_language, t

logger = logging.getLogger(__name__)
router = Router(name="webapp")


@router.message(Command("app"))
async def cmd_app(message: Message, session: AsyncSession) -> None:
    if not config.webapp_url.startswith("https://"):
        await message.answer(t("app_not_configured"))
        return
    user = await users.get_user(session, message.from_user.id)
    if user is None or user.profile is None:
        await message.answer(t("need_profile"))
        return
    plan = await plans.get_or_create_plan(session, user)
    if plan is None or not plan.days:
        await message.answer(t("plan_empty"))
        return
    active = await workouts.get_active(session, user)
    day_index = active.day_index if active is not None and active.day_index is not None \
        else await workouts.next_day_index(session, user, plan)
    day = plan.days[day_index]
    payload = await webapp.build_payload(session, user, plan, day_index, current_language(),
                                         day_label(day.name_key, day.suffix))
    # A reply-keyboard button (not an inline one): only these let the app send data back.
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_open_app"), web_app=WebAppInfo(url=webapp.app_url(payload)))]],
        resize_keyboard=True,
    )
    await message.answer(t("app_open", n=day_index + 1, name=day_label(day.name_key, day.suffix)),
                         reply_markup=keyboard)


@router.message(F.web_app_data)
async def on_app_data(message: Message, session: AsyncSession) -> None:
    user = await users.get_user(session, message.from_user.id)
    if user is None or user.profile is None:
        await message.answer(t("need_profile"), reply_markup=ReplyKeyboardRemove())
        return
    try:
        day_index, sets = webapp.parse_result(message.web_app_data.data)
        plan = await plans.get_plan(session, user)
        if plan is None:
            raise ValueError("no plan")
        summary, skipped = await webapp.apply_result(session, user, plan, day_index, sets)
    except (ValueError, KeyError, TypeError):
        logger.warning("Invalid data from the Mini App")
        await message.answer(t("app_bad_data"), reply_markup=main_menu_keyboard())
        return
    if summary is None:
        await message.answer(t("workout_discarded"), reply_markup=main_menu_keyboard())
        return
    logger.info("Workout logged from the Mini App (%s sets)", summary.total_sets)
    sync_user(user.id, await reminders.workout_finished(session, user))
    parts = [summary_text(summary, plan, day_index)]
    if skipped:
        parts.append(t("app_skipped", n=skipped))
    new = await achievements.check_new(session, user)
    parts += [p for p in (extras.streak_text(await achievements.compute_stats(session, user)),
                          extras.new_achievements_text(new)) if p]
    await message.answer("\n\n".join(parts), reply_markup=main_menu_keyboard())
    await extras.send_suggestions(message, session, user, calories=False)
