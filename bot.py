"""
Entry point: python bot.py

Wires together config, logging, database, middlewares and handlers, then
starts long polling.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent
from sqlalchemy.ext.asyncio import async_sessionmaker

from config import config
from database.base import create_tables, make_engine, make_session_factory
from handlers import get_routers
from services.exercise_import import ExerciseDataError, import_exercises, load_exercises_file
from services.exercises import get_injury_rules
from services.rest_timer import rest_timers
from utils.logging_setup import setup_logging
from utils.middlewares import DbSessionMiddleware, RateLimitMiddleware
from utils.texts import t

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="Start or resume setup"),
    BotCommand(command="profile", description="Your profile and daily targets"),
    BotCommand(command="workout", description="Start or continue today's workout"),
    BotCommand(command="plan", description="Your workout plan"),
    BotCommand(command="exercises", description="Exercise library"),
    BotCommand(command="settings", description="Edit profile and settings"),
    BotCommand(command="help", description="All commands"),
    BotCommand(command="about", description="About and credits"),
    BotCommand(command="deleteme", description="Delete all my data"),
]


async def on_error(event: ErrorEvent) -> bool:
    """Log any unhandled error and tell the user something went wrong."""
    logger.exception("Unhandled error in update %s", event.update.update_id,
                     exc_info=event.exception)
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(t("error"), show_alert=True)
        elif event.update.message:
            await event.update.message.answer(t("error"))
    except Exception:  # noqa: BLE001 - never let the error handler itself crash
        logger.warning("Could not notify user about the error")
    return True


def create_dispatcher(session_factory: async_sessionmaker,
                      rate_limit_max: int = config.rate_limit_max,
                      rate_limit_window: float = config.rate_limit_window) -> Dispatcher:
    # MemoryStorage loses half-finished forms on restart; switch to RedisStorage in production.
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    rate_limiter = RateLimitMiddleware(rate_limit_max, rate_limit_window)
    dp.message.outer_middleware(rate_limiter)
    dp.callback_query.outer_middleware(rate_limiter)

    dp["session_factory"] = session_factory  # handlers that work outside an update (rest timer)
    dp.include_routers(*get_routers())
    dp.errors.register(on_error)
    return dp


async def main() -> None:
    setup_logging(config.log_level)

    if not config.bot_token:
        logger.error("BOT_TOKEN is not set. Copy .env.example to .env and add your token.")
        sys.exit(1)

    engine = make_engine(config.database_url)
    await create_tables(engine)
    session_factory = make_session_factory(engine)

    # Keep the exercises table in sync with data/core_exercises.json.
    try:
        records = load_exercises_file()
        get_injury_rules()  # validates data/injury_exclusions.json too
        async with session_factory() as session:
            await import_exercises(session, records)
    except ExerciseDataError as error:
        logger.error("%s", error)
        await engine.dispose()
        sys.exit(1)

    dp = create_dispatcher(session_factory)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot started")
        await dp.start_polling(bot)
    finally:
        rest_timers.cancel_all()
        await bot.session.close()
        await engine.dispose()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
