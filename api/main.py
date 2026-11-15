"""
Gym24 API: the backend for the Telegram Mini App.

One backend, two entry points, one database:
    python bot.py                         the Telegram bot (chat, reminders)
    uvicorn api.main:app --port 8000      this API (+ serves the Mini App)

Both use the same models (database/), services (services/) and texts (locales/).
Interactive API docs: http://localhost:8000/api/docs
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.notify import Notifier, make_notifier, no_notifier
from api.routes import exercises, me, plan, profile, system, train
from api.static import CachedStaticFiles, MiniAppFiles
from config import config
from database.base import make_engine, make_session_factory
from database.migrate import prepare_database
from utils.logging_setup import setup_logging
from utils.rate_limit import SlidingWindowLimiter

logger = logging.getLogger("api")

ROOT = Path(__file__).resolve().parent.parent
EXERCISE_IMAGES = ROOT / "assets" / "exercises"
MINIAPP_BUILD = ROOT / "miniapp" / "dist"


def create_app(session_factory: async_sessionmaker | None = None,
               bot_token: str | None = None, notifier: Notifier | None = None,
               exercise_images: Path | None = None, admin_ids: set[int] | None = None) -> FastAPI:
    """Build the app. Tests pass their own session factory and a fake token."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = None
        if session_factory is None:
            setup_logging(config.log_level)
            if not app.state.bot_token:
                raise RuntimeError("BOT_TOKEN is not set. The API needs it to verify Mini App logins.")
            engine = make_engine(config.database_url)
            await prepare_database(engine)
            app.state.session_factory = make_session_factory(engine)
            logger.info("API started")
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title="Gym24 API", version="0.1.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

    app.state.bot_token = bot_token if bot_token is not None else config.bot_token
    app.state.session_factory = session_factory
    app.state.init_data_max_age = config.init_data_max_age
    app.state.user_limiter = SlidingWindowLimiter(config.api_rate_limit, 60)
    app.state.auth_fail_limiter = SlidingWindowLimiter(20, 60)
    # Chat message after Mini App onboarding. Tests pass their own (or get none).
    if notifier is None:
        notifier = make_notifier(app.state.bot_token) if session_factory is None else no_notifier
    app.state.notifier = notifier
    app.state.exercise_images = exercise_images or EXERCISE_IMAGES
    app.state.admin_ids = set(config.admin_ids if admin_ids is None else admin_ids)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - log it and answer with a clean 500
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse({"detail": "internal_error"}, status_code=500)
        if request.url.path.startswith("/api"):
            logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path,
                        response.status_code, (time.perf_counter() - started) * 1000)
        return response

    app.include_router(system.router)
    app.include_router(me.router)
    app.include_router(profile.router)
    app.include_router(exercises.router)
    app.include_router(plan.router)        # Stage 4: programs, split editor, calendar, energy
    app.include_router(train.router)       # Stage 5: workout-day screen and live logger

    # Exercise images (public, no user data), cached for a week.
    app.mount("/static/exercises",
              CachedStaticFiles(directory=app.state.exercise_images, check_dir=False), name="exercises")
    # The built Mini App, if present (npm run build in miniapp/). Mounted last.
    if MINIAPP_BUILD.is_dir():
        app.mount("/", MiniAppFiles(directory=MINIAPP_BUILD, html=True), name="miniapp")
    return app


app = create_app()
