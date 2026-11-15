"""
/app: open the Gym24 Mini App.

It's opened with an INLINE web_app button (under the message). Telegram only
sends the signed login data (initData) for inline buttons and the menu button,
never for reply-keyboard buttons, and the app needs that data to log you in.

The old Phase 6 logger used a reply-keyboard button and sent the finished
workout back as web_app_data; on_app_data stays so old buttons still work.
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from handlers import extras
from handlers.workout import summary_text
from keyboards.menu import main_menu_keyboard, miniapp_ready, open_app_button
from services import achievements, plans, reminders, users, webapp
from services.scheduler import sync_user
from utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="webapp")


@router.message(Command("app"))
async def cmd_app(message: Message, session: AsyncSession) -> None:
    if not miniapp_ready():
        await message.answer(t("app_not_ready"))
        return
    user = await users.get_user(session, message.from_user.id)
    if user is None or user.profile is None:
        # No profile yet: the app opens on onboarding.
        button = open_app_button("", "btn_setup_in_app")
        await message.answer(t("start_setup_in_app"), reply_markup=ReplyKeyboardRemove())
        await message.answer(t("app_open_now"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))
        return
    # Replace the old "Open workout logger" reply button with the normal menu...
    await message.answer(t("menu_main"), reply_markup=main_menu_keyboard())
    # ...and open the app on the Train tab with an inline button.
    button = open_app_button("workout")
    await message.answer(t("app_open_now"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))


@router.message(F.web_app_data)
async def on_app_data(message: Message, session: AsyncSession) -> None:
    """Finished workouts from the old Phase 6 logger (kept for old buttons)."""
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
