"""Stage 3 fix: every exercise has a visual_type ("images" for now) and the API returns it."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import api.main as api_main
from database.models import Exercise
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_api import TOKEN, auth, sign_init_data

USER = {"id": 7101, "first_name": "Vera", "language_code": "en"}


@pytest_asyncio.fixture
async def client(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=tmp_path, admin_ids=set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_imported_exercises_default_to_images(session_factory):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
        kinds = set((await s.execute(select(Exercise.visual_type))).scalars())
    assert kinds == {"images"}


async def test_detail_returns_visual_type(client):
    response = await client.get("/api/exercises/bench-press", headers=auth(sign_init_data(USER)))
    assert response.status_code == 200, response.text
    assert response.json()["visual_type"] == "images"
