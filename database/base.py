"""
Database engine and session factory.

Only the DATABASE_URL changes when moving from SQLite to PostgreSQL;
the models and services stay the same.
"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """All models inherit from this."""


def make_engine(url: str) -> AsyncEngine:
    engine = create_async_engine(url)

    if url.startswith("sqlite"):
        # SQLite ignores foreign keys (and ON DELETE CASCADE) unless switched on
        # per connection. /deleteme relies on cascades, so this matters.
        # WAL + busy_timeout let the bot and the API (two processes) share one
        # database file without "database is locked" errors.
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            if ":memory:" not in url:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    # expire_on_commit=False lets us read attributes after commit without a new query.
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """
    Create missing tables. Fine for development; before going to production
    with PostgreSQL we'll switch to Alembic migrations.
    """
    from database import models  # noqa: F401  (registers the models)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
