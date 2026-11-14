"""/start, /help, /about, /cancel, /language and the health disclaimer."""
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from handlers.onboarding import ask_step, send_or_edit, start_onboarding, step_from_state
from keyboards.profile import LangCB, MenuCB, disclaimer_keyboard, language_keyboard
from services import users
from utils.commands import set_chat_commands
from utils.texts import SUPPORTED_LANGUAGES, set_language, t

logger = logging.getLogger(__name__)
router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await users.get_or_create_user(
        session, message.from_user.id, message.from_user.language_code
    )

    if user.profile is not None:
        await state.clear()
        await message.answer(t("start_welcome_back"))
        return

    if user.disclaimer_accepted_at is None:
        await message.answer(t("disclaimer"), reply_markup=disclaimer_keyboard())
        return

    # Halfway through onboarding? Repeat the current question instead of restarting.
    step = await step_from_state(state)
    if step is not None and (await state.get_data()).get("mode") == "onboarding":
        await ask_step(message, state, step)
        return

    await start_onboarding(message, state)


@router.callback_query(MenuCB.filter(F.action == "accept_disclaimer"))
async def on_accept_disclaimer(callback: CallbackQuery, state: FSMContext,
                               session: AsyncSession) -> None:
    user = await users.get_or_create_user(
        session, callback.from_user.id, callback.from_user.language_code
    )
    await callback.answer()
    # Keep the disclaimer text visible, just remove the button.
    await callback.message.edit_reply_markup(reply_markup=None)

    if user.disclaimer_accepted_at is None:
        await users.accept_disclaimer(session, user)
    if user.profile is not None:
        await callback.message.answer(t("start_welcome_back"))
        return

    await callback.message.answer(t("onboarding_intro"))
    await start_onboarding(callback.message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(t("help"))


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer(t("about", attribution=config.exercise_image_attribution))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(t("nothing_to_cancel"))
        return
    await state.clear()
    await message.answer(t("cancelled"))


# ---------- Language ----------

@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    await message.answer(t("language_pick"), reply_markup=language_keyboard())


@router.callback_query(MenuCB.filter(F.action == "language"))
async def on_language_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(t("language_pick"), reply_markup=language_keyboard())


@router.callback_query(LangCB.filter())
async def on_language(callback: CallbackQuery, callback_data: LangCB, bot: Bot,
                      session: AsyncSession) -> None:
    if callback_data.code not in SUPPORTED_LANGUAGES:
        await callback.answer(t("stale_button"))
        return
    user = await users.get_or_create_user(session, callback.from_user.id,
                                          callback.from_user.language_code)
    user.language_code = callback_data.code
    await session.commit()
    lang = set_language(callback_data.code)  # the rest of this reply uses the new language
    await callback.answer()
    try:
        await set_chat_commands(bot, callback.message.chat.id, lang)
    except TelegramBadRequest:
        logger.warning("Could not update the command menu language")

    if user.disclaimer_accepted_at is None:
        # Still on the first screen: show the disclaimer again in the new language.
        await send_or_edit(callback, t("disclaimer"), disclaimer_keyboard())
    else:
        await send_or_edit(callback, t("language_changed"))
