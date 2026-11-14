"""/profile, /settings, profile editing and /deleteme."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.onboarding import STEPS, send_or_edit, show_profile, start_edit
from keyboards.profile import (
    EditCB,
    MenuCB,
    delete_confirm_keyboard,
    edit_fields_keyboard,
    settings_keyboard,
)
from services import users
from services.scheduler import sync_user
from utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="profile")


async def _load_profile(event: Message | CallbackQuery, session: AsyncSession):
    """Return the user's profile, or tell them to run /start and return None."""
    user = await users.get_user(session, event.from_user.id)
    if user is None or user.profile is None:
        if isinstance(event, CallbackQuery):
            await event.answer()
        await send_or_edit(event, t("need_profile"))
        return None
    return user.profile


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    profile = await _load_profile(message, session)
    if profile:
        await show_profile(message, profile)


@router.callback_query(MenuCB.filter(F.action == "profile"))
async def on_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    profile = await _load_profile(callback, session)
    if profile:
        await callback.answer()
        await show_profile(callback, profile)


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    await message.answer(t("settings"), reply_markup=settings_keyboard())


@router.callback_query(MenuCB.filter(F.action == "show_disclaimer"))
async def on_show_disclaimer(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(t("disclaimer"))


# ---------- Editing ----------

@router.callback_query(MenuCB.filter(F.action == "edit"))
async def on_edit_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    profile = await _load_profile(callback, session)
    if profile:
        await callback.answer()
        await send_or_edit(callback, t("edit_pick_field"), edit_fields_keyboard(STEPS))


@router.callback_query(EditCB.filter())
async def on_edit_field(callback: CallbackQuery, callback_data: EditCB,
                        state: FSMContext, session: AsyncSession) -> None:
    if callback_data.field not in STEPS:
        await callback.answer(t("stale_button"))
        return
    profile = await _load_profile(callback, session)
    if profile:
        await callback.answer()
        await start_edit(callback, state, profile, callback_data.field)


# ---------- Delete all data ----------

@router.message(Command("deleteme"))
async def cmd_deleteme(message: Message) -> None:
    await message.answer(t("delete_confirm"), reply_markup=delete_confirm_keyboard())


@router.callback_query(MenuCB.filter(F.action == "delete"))
async def on_delete(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_or_edit(callback, t("delete_confirm"), delete_confirm_keyboard())


@router.callback_query(MenuCB.filter(F.action == "delete_yes"))
async def on_delete_yes(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    user = await users.get_user(session, callback.from_user.id)
    if user is not None:
        sync_user(user.id, None)  # stop their reminders
    deleted = await users.delete_user_data(session, callback.from_user.id)
    await state.clear()  # forget any half-finished form answers too
    await send_or_edit(callback, t("delete_done" if deleted else "delete_nothing"))


@router.callback_query(MenuCB.filter(F.action == "delete_no"))
async def on_delete_no(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_or_edit(callback, t("delete_kept"))
