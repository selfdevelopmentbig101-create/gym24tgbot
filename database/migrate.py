"""
Database migrations, applied automatically when the bot or the API starts.

- New database: Alembic creates every table (migrations/versions/).
- Database from before migrations existed (Phases 1-6 used create_all):
  "adopted" once. Missing tables and columns are added, obsolete columns are
  dropped, existing data is kept, and it's marked as up to date. After that,
  every schema change goes through a normal Alembic migration.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from database.base import Base
from database import models  # noqa: F401  (registers every table)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

# Columns that existed before migrations and were removed since.
# users.language_code: Telegram's app language, auto-saved at sign-up. Replaced by
# users.language, which is only set when the user actually chooses (so existing
# users are asked once, as planned).
OBSOLETE_COLUMNS = {"users": ["language_code"]}


def _alembic_config(connection: Connection) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


def _column_sql(connection: Connection, column) -> str:
    """'name TYPE [NOT NULL DEFAULT x]' for ALTER TABLE ADD COLUMN."""
    type_sql = column.type.compile(dialect=connection.dialect)
    default = column.default.arg if column.default is not None and column.default.is_scalar else None
    if default is None and column.server_default is not None:
        server = str(column.server_default.arg)
        if not column.nullable:
            return f'"{column.name}" {type_sql} NOT NULL DEFAULT \'{server}\''
    if column.nullable or default is None:
        # SQLite can't add a NOT NULL column without a default; nullable is safe here.
        return f'"{column.name}" {type_sql}'
    if isinstance(default, bool):
        default = int(default)
    literal = f"'{default}'" if isinstance(default, str) else str(default)
    return f'"{column.name}" {type_sql} NOT NULL DEFAULT {literal}'


def _adopt_legacy(connection: Connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    # 1. Missing tables (checkfirst leaves existing ones alone).
    Base.metadata.create_all(connection, checkfirst=True)

    # 2. Missing columns in tables that already existed.
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in have:
                logger.info("Adding column %s.%s", table.name, column.name)
                connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN '
                                        f'{_column_sql(connection, column)}'))

    # 3. Obsolete columns.
    for table_name, columns in OBSOLETE_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table_name)}
        for name in columns:
            if name in have:
                logger.info("Dropping obsolete column %s.%s", table_name, name)
                connection.execute(text(f'ALTER TABLE "{table_name}" DROP COLUMN "{name}"'))

    # 4. Indexes whose uniqueness changed (e.g. one plan per user -> several programs).
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        old = {i["name"]: bool(i["unique"]) for i in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in old and old[index.name] != bool(index.unique):
                logger.info("Recreating index %s", index.name)
                connection.execute(text(f'DROP INDEX "{index.name}"'))
                index.create(connection)

    # 5. Programs (Stage 4): existing plans become the current program.
    if "workout_plans" in existing_tables:
        connection.execute(text(
            "UPDATE workout_plans SET template_days = (SELECT COUNT(*) FROM plan_days "
            "WHERE plan_days.plan_id = workout_plans.id), started_on = DATE(created_at) "
            "WHERE template_days IS NULL AND kind = 'template'"))


def _prepare(connection: Connection) -> None:
    tables = set(inspect(connection).get_table_names())
    cfg = _alembic_config(connection)
    if "alembic_version" not in tables and "users" in tables:
        logger.info("Existing database without migrations: adopting it (one time)")
        _adopt_legacy(connection)
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")


async def prepare_database(engine: AsyncEngine) -> None:
    """Bring the database schema up to date. Safe to call on every start."""
    async with engine.begin() as connection:
        await connection.run_sync(_prepare)
    logger.info("Database schema is up to date")
