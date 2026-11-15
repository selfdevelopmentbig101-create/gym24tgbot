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
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent, MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import async_sessionmaker

from config import config
from database.base import make_engine, make_session_factory
from database.migrate import prepare_database
from handlers import get_routers
from handlers.reminders import make_notifier
from services.exercise_import import ExerciseDataError, import_exercises, load_exercises_file
from services.exercises import get_injury_rules
from services.foods import FoodDataError, all_foods
from services.rest_timer import rest_timers
from services.scheduler import ReminderScheduler, set_scheduler
from utils.commands import set_default_commands
from utils.logging_setup import setup_logging
from utils.middlewares import DbSessionMiddleware, LanguageMiddleware, RateLimitMiddleware
from utils.texts import t

logger = logging.getLogger(__name__)



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
    dp.update.outer_middleware(LanguageMiddleware())  # needs the session, so registered second
    rate_limiter = RateLimitMiddleware(rate_limit_max, rate_limit_window)
    dp.message.outer_middleware(rate_limiter)
    dp.callback_query.outer_middleware(rate_limiter)

    dp["session_factory"] = session_factory  # handlers that work outside an update (rest timer)
    dp.include_routers(*get_routers())
    dp.errors.register(on_error)
    return dp


async def set_miniapp_menu_button(bot: Bot) -> None:
    """
    Make the chat menu button (left of the message box) open the Gym24 Mini App.
    Done here instead of in BotFather, so a new tunnel URL only needs a .env change.
    The menu button sends signed initData (a reply-keyboard button would not).
    """
    if not config.miniapp_url:
        return
    if not config.miniapp_url.startswith("https://"):
        logger.warning("MINIAPP_URL must start with https:// (Telegram requires HTTPS)")
        return
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
            text="Gym24", web_app=WebAppInfo(url=config.miniapp_url)))
        logger.info("Menu button opens the Mini App at %s", config.miniapp_url)
    except TelegramBadRequest as error:
        logger.warning("Could not set the Mini App menu button: %s", error)


async def main() -> None:
    setup_logging(config.log_level)

    if not config.bot_token:
        logger.error("BOT_TOKEN is not set. Copy .env.example to .env and add your token.")
        sys.exit(1)

    engine = make_engine(config.database_url)
    await prepare_database(engine)  # applies migrations (and adopts old databases once)
    session_factory = make_session_factory(engine)

    # Keep the exercises table in sync with data/core_exercises.json.
    try:
        records = load_exercises_file()
        get_injury_rules()  # validates data/injury_exclusions.json too
        all_foods()  # validates data/foods.json
        async with session_factory() as session:
            await import_exercises(session, records)
    except (ExerciseDataError, FoodDataError) as error:
        logger.error("%s", error)
        await engine.dispose()
        sys.exit(1)

    dp = create_dispatcher(session_factory)

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Reminders: rebuild every user's jobs from the database.
    scheduler = ReminderScheduler(make_notifier(bot, session_factory))
    set_scheduler(scheduler)
    scheduler.start()
    async with session_factory() as session:
        await scheduler.load_all(session)

    try:
        await set_default_commands(bot)
        await set_miniapp_menu_button(bot)
        logger.info("Bot started")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        set_scheduler(None)
        rest_timers.cancel_all()
        await bot.session.close()
        await engine.dispose()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
