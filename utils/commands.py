"""The bot's command menu, in each language."""
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from utils.texts import SUPPORTED_LANGUAGES, t

COMMANDS = ("start", "workout", "plan", "food", "progress", "weight", "achievements", "app",
            "reminders", "exercises", "profile", "premium", "language", "settings", "help",
            "about", "deleteme")


def bot_commands(lang: str) -> list[BotCommand]:
    return [BotCommand(command=name, description=t(f"cmd_{name}", lang)) for name in COMMANDS]


async def set_default_commands(bot: Bot) -> None:
    """English for everyone, plus Russian/Uzbek for users whose Telegram app uses them."""
    await bot.set_my_commands(bot_commands("en"))
    for lang in SUPPORTED_LANGUAGES:
        if lang != "en":
            await bot.set_my_commands(bot_commands(lang), language_code=lang)


async def set_chat_commands(bot: Bot, chat_id: int, lang: str) -> None:
    """After /language: show this user's menu in their chosen language."""
    await bot.set_my_commands(bot_commands(lang), scope=BotCommandScopeChat(chat_id=chat_id))
