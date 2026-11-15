"""
Alembic environment: how migrations connect to the database.

Two ways in:
- From our code (database/migrate.py): a ready connection is passed in
  config.attributes["connection"], so migrations run inside the app's own engine.
- From the command line (`alembic upgrade head`): we open an async engine for
  DATABASE_URL ourselves.
"""
import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from config import config as app_config
from database.base import Base, make_engine
from database import models  # noqa: F401  (registers every table on Base.metadata)

target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite can't ALTER most things in place; "batch" mode copies the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = make_engine(app_config.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) mode isn't used in this project.")

existing = context.config.attributes.get("connection")
if existing is not None:
    _run(existing)
else:
    asyncio.run(_run_async())
