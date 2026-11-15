"""
Migrations: a new database gets the full schema, and a database from before
migrations (Phases 1-6) is adopted once without losing data.
"""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, inspect, text

from database.base import Base, make_engine
from database.migrate import ROOT, prepare_database


def _head() -> str:
    from alembic.config import Config
    return ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()


async def _state(engine):
    """(alembic version, schema differences vs the models, users columns)."""
    async with engine.connect() as conn:
        def read(sync_conn):
            version = sync_conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            diffs = compare_metadata(MigrationContext.configure(sync_conn), Base.metadata)
            columns = {c["name"] for c in inspect(sync_conn).get_columns("users")}
            return version, diffs, columns
        return await conn.run_sync(read)


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


async def test_new_database_gets_full_schema(db_url):
    engine = make_engine(db_url)
    await prepare_database(engine)
    version, diffs, columns = await _state(engine)
    assert version == _head()
    assert diffs == []                       # migrations match the models exactly
    assert "language" in columns and "language_code" not in columns
    await prepare_database(engine)           # second start: nothing to do
    await engine.dispose()


async def test_phase1_database_is_adopted_and_keeps_data(db_url):
    engine = make_engine(db_url)
    # Rebuild the Phase 1 schema the way it was made (create_all, no alembic_version),
    # then strip what later phases added and restore the old users.language_code.
    phase1 = MetaData()
    for name in ("users", "profiles", "exercises"):
        Base.metadata.tables[name].to_metadata(phase1)
    async with engine.begin() as conn:
        await conn.run_sync(phase1.create_all)
        for sql in (
            "ALTER TABLE users DROP COLUMN language",
            "ALTER TABLE users DROP COLUMN premium_until",
            "ALTER TABLE users DROP COLUMN trial_used",
            "ALTER TABLE users ADD COLUMN language_code VARCHAR(8) NOT NULL DEFAULT 'en'",
            "ALTER TABLE profiles DROP COLUMN calorie_adjust",
            "ALTER TABLE profiles DROP COLUMN kcal_offered_at",
            "ALTER TABLE profiles DROP COLUMN deload_until",
            "ALTER TABLE profiles DROP COLUMN deload_offered_at",
            "ALTER TABLE profiles DROP COLUMN target_weight_kg",
            "ALTER TABLE exercises DROP COLUMN active",
            "ALTER TABLE exercises DROP COLUMN sort_order",
            "ALTER TABLE exercises DROP COLUMN secondary_muscles",
            "INSERT INTO users (id, telegram_id, created_at, disclaimer_accepted_at, language_code) "
            "VALUES (1, 4242, '2026-11-01 10:00:00', '2026-11-01 10:01:00', 'ru')",
            "INSERT INTO profiles VALUES (1, 1, 'lean_bulk', 27, 'male', 180, 75, 'beginner', 3, "
            "'full_gym', '[]', 'none', '2026-11-01 10:02:00')",
        ):
            await conn.execute(text(sql))

    await prepare_database(engine)

    version, diffs, columns = await _state(engine)
    assert version == _head()
    assert "language" in columns and "language_code" not in columns
    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT telegram_id, language FROM users"))).one()
        assert tuple(row) == (4242, None)    # data kept; language must be chosen once
        profile = (await conn.execute(text(
            "SELECT goal, weight_kg, calorie_adjust FROM profiles"))).one()
        assert tuple(profile) == ("lean_bulk", 75, 0)   # new column got its default
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert set(Base.metadata.tables) <= tables

    # The adopted schema must match the models (no missing tables, columns or indexes).

    assert diffs == []

    await prepare_database(engine)           # second start: already adopted
    await engine.dispose()


async def test_upgrade_from_0001_keeps_profiles(db_url):
    """A database already on migrations gets later revisions applied in place."""
    from alembic import command
    from database.migrate import _alembic_config

    engine = make_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: command.upgrade(_alembic_config(c), "0001"))
        await conn.execute(text(
            "INSERT INTO users (id, telegram_id, created_at, trial_used) "
            "VALUES (1, 4242, '2026-11-01 10:00:00', 0)"))
        await conn.execute(text(
            "INSERT INTO profiles (id, user_id, goal, age, sex, height_cm, weight_kg, experience, "
            "training_days, equipment, injuries, diet, calorie_adjust, updated_at) VALUES "
            "(1, 1, 'bulk', 30, 'female', 165, 60, 'beginner', 3, 'full_gym', '[]', 'none', 0, "
            "'2026-11-01 10:02:00')"))

    await prepare_database(engine)

    version, diffs, _ = await _state(engine)
    assert version == _head() and diffs == []
    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT goal, weight_kg, target_weight_kg FROM profiles"))).one()
    assert tuple(row) == ("bulk", 60, None)
    await engine.dispose()
