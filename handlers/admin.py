"""
Admin commands, only for Telegram user IDs listed in ADMIN_IDS (.env).
For everyone else these commands simply don't exist.

/admin            bot statistics
/broadcast <text> preview a message, then Send to every user
"""
import asyncio
import logging
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import BodyWeightLog, MealLog, Profile, User, WorkoutSession, utcnow
from handlers.onboarding import send_or_edit
from keyboards.extras import AdminCB, broadcast_keyboard
from utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="admin")

BROADCAST_DELAY = 0.05  # ~20 messages/second, under Telegram's ~30/s limit


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in config.admin_ids


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def bot_stats(session: AsyncSession) -> dict[str, int]:
    week_ago = utcnow() - timedelta(days=7)

    async def count(query) -> int:
        return await session.scalar(query) or 0

    active = union(
        select(WorkoutSession.user_id).where(WorkoutSession.started_at >= week_ago),
        select(MealLog.user_id).where(MealLog.logged_at >= week_ago),
        select(BodyWeightLog.user_id).where(BodyWeightLog.logged_at >= week_ago),
    ).subquery()
    return {
        "users": await count(select(func.count()).select_from(User)),
        "profiles": await count(select(func.count()).select_from(Profile)),
        "new_7d": await count(select(func.count()).select_from(User).where(User.created_at >= week_ago)),
        "active_7d": await count(select(func.count()).select_from(active)),
        "workouts_7d": await count(
            select(func.count()).select_from(WorkoutSession)
            .where(WorkoutSession.finished_at >= week_ago)),
    }


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    await message.answer(t("admin_stats", **await bot_stats(session)))


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject, state: FSMContext) -> None:
    text = (command.args or "").strip()
    if not text:
        await message.answer(t("broadcast_usage"))
        return
    try:
        # The preview also checks the HTML formatting is valid before sending to everyone.
        await message.answer(text)
    except TelegramBadRequest as error:
        await message.answer(t("broadcast_bad_html", error=str(error)), parse_mode=None)
        return
    await state.update_data(broadcast=text)
    await message.answer(t("broadcast_confirm"), reply_markup=broadcast_keyboard())


@router.callback_query(AdminCB.filter(F.a == "cancel"))
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(broadcast=None)
    await callback.answer()
    await send_or_edit(callback, t("broadcast_cancelled"))


@router.callback_query(AdminCB.filter(F.a == "send"))
async def on_send(callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext) -> None:
    text = (await state.get_data()).get("broadcast")
    if not text:
        await callback.answer(t("stale_button"))
        return
    await state.update_data(broadcast=None)  # a double tap must not send twice
    await callback.answer()
    recipients = list(await session.scalars(select(User.telegram_id)))
    await send_or_edit(callback, t("broadcast_sending", n=len(recipients)))
    sent, blocked, failed = await broadcast(bot, recipients, text)
    logger.info("Broadcast: %s sent, %s blocked, %s failed", sent, blocked, failed)
    await callback.message.answer(t("broadcast_done", sent=sent, blocked=blocked, failed=failed))


async def broadcast(bot: Bot, recipients: list[int], text: str,
                    delay: float = BROADCAST_DELAY) -> tuple[int, int, int]:
    sent = blocked = failed = 0
    for chat_id in recipients:
        for attempt in range(2):
            try:
                await bot.send_message(chat_id, text)
                sent += 1
            except TelegramRetryAfter as error:
                if attempt == 0:
                    await asyncio.sleep(error.retry_after)
                    continue  # retry once after Telegram's requested pause
                failed += 1
            except TelegramForbiddenError:
                blocked += 1  # user blocked the bot
            except TelegramBadRequest:
                failed += 1   # e.g. chat not found
            break
        await asyncio.sleep(delay)
    return sent, blocked, failed
