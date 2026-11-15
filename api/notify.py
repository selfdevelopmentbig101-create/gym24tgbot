"""
Messages from the API to the user's chat. After onboarding in the Mini App, the
chat gets the main menu, so the bot and the app stay in step.
"""
import logging
from typing import Awaitable, Callable

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from keyboards.menu import main_menu_keyboard
from utils.texts import set_language, t

logger = logging.getLogger(__name__)

Notifier = Callable[[int, str], Awaitable[None]]


def make_notifier(bot_token: str) -> Notifier:
    async def notify_setup_done(telegram_id: int, lang: str) -> None:
        set_language(lang)
        bot = Bot(bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            await bot.send_message(telegram_id, t("app_setup_done"), reply_markup=main_menu_keyboard())
        except TelegramAPIError as error:
            # e.g. the user never pressed Start in the chat: the app still works.
            logger.warning("Could not send the setup message to the chat: %s", error)
        finally:
            await bot.session.close()
    return notify_setup_done


async def no_notifier(telegram_id: int, lang: str) -> None:
    """Tests and setups without a bot token."""
