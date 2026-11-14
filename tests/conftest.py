import sys
from pathlib import Path

import pytest_asyncio

# Make the project root importable (so "import services" works).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.base import create_tables, make_engine, make_session_factory  # noqa: E402


@pytest_asyncio.fixture
async def session_factory():
    """A fresh in-memory SQLite database for each test."""
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    yield make_session_factory(engine)
    await engine.dispose()
