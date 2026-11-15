"""/exercises: browse the exercise library by muscle group."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.cards import library_card, show_card
from handlers.onboarding import send_or_edit
from keyboards.menu import MenuButton
from keyboards.exercises import LibCB, groups_keyboard
from services import exercises as exercise_service
from services import users
from utils.texts import t

router = Router(name="library")


async def _groups_view(session: AsyncSession, telegram_id: int):
    user = await users.get_user(session, telegram_id)
    groups = await exercise_service.muscle_groups(session)
    if not groups:
        return t("no_exercises_loaded"), None
    key = "library_pick_group_filtered" if user and user.profile else "library_pick_group"
    return t(key), groups_keyboard(groups)


@router.message(Command("exercises"))
@router.message(MenuButton("menu_exercises"))
async def cmd_exercises(message: Message, session: AsyncSession) -> None:
    text, keyboard = await _groups_view(session, message.from_user.id)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(LibCB.filter(F.group == ""))
async def on_groups(callback: CallbackQuery, session: AsyncSession) -> None:
    text, keyboard = await _groups_view(session, callback.from_user.id)
    await callback.answer()
    if callback.message.text:
        await send_or_edit(callback, text, keyboard)
    else:
        # Coming back from a card with an image: a photo can't become text, so replace it.
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(LibCB.filter(F.group != ""))
async def on_group(callback: CallbackQuery, callback_data: LibCB, session: AsyncSession) -> None:
    user = await users.get_user(session, callback.from_user.id)
    card = await library_card(session, user.profile if user else None, callback_data.group)
    if card is None:
        await callback.answer(t("library_empty"), show_alert=True)
        return
    await callback.answer()
    await show_card(callback, session, card)
