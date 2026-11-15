"""/start, /help, /about, /cancel, /language, the health disclaimer and the main menu.

New users set up their profile in the Mini App (one question per screen, with the
health disclaimer there). /start only shows the button that opens it. The old
chat questionnaire is used only when the Mini App isn't configured (MINIAPP_URL
is not an https:// address), so the bot keeps working without a tunnel.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import User
from handlers.onboarding import ask_step, send_or_edit, start_onboarding, step_from_state
from keyboards.menu import (MenuButton, main_menu_keyboard, miniapp_ready, open_app_button,
                            send_main_menu, settings_menu_keyboard)
from keyboards.profile import (LangCB, MenuCB, disclaimer_keyboard, first_language_prompt,
                               language_keyboard)
from services import users
from utils.commands import set_chat_commands
from utils.texts import SUPPORTED_LANGUAGES, set_language, t

logger = logging.getLogger(__name__)
router = Router(name="common")


async def send_app_setup(message: Message, state: FSMContext) -> None:
    """Welcome (with a short health note) and the button that opens onboarding in the Mini App."""
    await state.clear()  # drop a half-finished chat questionnaire, if any
    button = open_app_button("", "btn_setup_in_app")
    await message.answer(t("start_setup_in_app"),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))


async def continue_start(message: Message, state: FSMContext, user: User) -> None:
    """Everything /start does once the language is known."""
    if user.profile is not None:
        await state.clear()
        await send_main_menu(message, t("start_welcome_back"))
        return

    if miniapp_ready():
        # Onboarding happens in the Mini App; the disclaimer is shown there too.
        await send_app_setup(message, state)
        return

    # ---- Fallback without the Mini App: the chat questionnaire ----
    if user.disclaimer_accepted_at is None:
        await message.answer(t("disclaimer"), reply_markup=disclaimer_keyboard())
        return

    # Halfway through onboarding? Repeat the current question instead of restarting.
    step = await step_from_state(state)
    if step is not None and (await state.get_data()).get("mode") == "onboarding":
        await ask_step(message, state, step)
        return

    await start_onboarding(message, state)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await users.get_or_create_user(session, message.from_user.id)
    if user.language is None:
        # Asked once: the choice is saved and shared with the Mini App.
        await message.answer(first_language_prompt(), reply_markup=language_keyboard(first=True))
        return
    await continue_start(message, state, user)


@router.callback_query(MenuCB.filter(F.action == "accept_disclaimer"))
async def on_accept_disclaimer(callback: CallbackQuery, state: FSMContext,
                               session: AsyncSession) -> None:
    user = await users.get_or_create_user(
        session, callback.from_user.id
    )
    await callback.answer()
    # Keep the disclaimer text visible, just remove the button.
    await callback.message.edit_reply_markup(reply_markup=None)

    if user.disclaimer_accepted_at is None:
        await users.accept_disclaimer(session, user)
    if user.profile is not None:
        await send_main_menu(callback.message, t("start_welcome_back"))
        return
    if miniapp_ready():
        await send_app_setup(callback.message, state)
        return

    await callback.message.answer(t("onboarding_intro"))
    await start_onboarding(callback.message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(t("help"))


def _about_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_disclaimer"), callback_data=MenuCB(action="show_disclaimer"))
    return builder.as_markup()


@router.message(Command("about"))
@router.message(MenuButton("menu_about"))
async def cmd_about(message: Message) -> None:
    await message.answer(t("about", attribution=config.exercise_image_attribution),
                         reply_markup=_about_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(t("nothing_to_cancel"))
        return
    await state.clear()
    await message.answer(t("cancelled"))


# ---------- Menus ----------

@router.message(Command("settings"))
@router.message(MenuButton("menu_settings"))
async def cmd_settings(message: Message) -> None:
    await message.answer(t("settings_menu"), reply_markup=settings_menu_keyboard())


@router.message(MenuButton("menu_back"))
async def on_back_to_menu(message: Message) -> None:
    await message.answer(t("menu_main"), reply_markup=main_menu_keyboard())


# ---------- Language ----------

@router.message(Command("language"))
@router.message(MenuButton("menu_language"))
async def cmd_language(message: Message) -> None:
    await message.answer(t("language_pick"), reply_markup=language_keyboard())


@router.callback_query(MenuCB.filter(F.action == "language"))
async def on_language_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(t("language_pick"), reply_markup=language_keyboard())


@router.callback_query(LangCB.filter())
async def on_language(callback: CallbackQuery, callback_data: LangCB, bot: Bot,
                      state: FSMContext, session: AsyncSession) -> None:
    if callback_data.code not in SUPPORTED_LANGUAGES:
        await callback.answer(t("stale_button"))
        return
    user = await users.get_or_create_user(session, callback.from_user.id)
    await users.set_language(session, user, callback_data.code)
    lang = set_language(callback_data.code)  # the rest of this reply uses the new language
    await callback.answer()
    try:
        await set_chat_commands(bot, callback.message.chat.id, lang)
    except TelegramBadRequest:
        logger.warning("Could not update the command menu language")

    if user.disclaimer_accepted_at is None and not miniapp_ready():
        # Chat setup only: show the disclaimer (again) in the new language.
        await send_or_edit(callback, t("disclaimer"), disclaimer_keyboard())
        return

    await send_or_edit(callback, t("language_changed"))
    if callback_data.first or (user.profile is None and miniapp_ready()):
        await continue_start(callback.message, state, user)
    else:
        # Re-send the menu so its labels are in the new language.
        await callback.message.answer(t("menu_main"), reply_markup=main_menu_keyboard())
