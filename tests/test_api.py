"""
API tests. initData is signed here exactly as Telegram signs it, with a test
bot token, so the real verification code runs.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from api.auth import InitDataError, verify_init_data
from services import users

TOKEN = "123456:TEST-TOKEN-not-real"


def sign_init_data(user: dict | None, token: str = TOKEN, auth_date: int | None = None,
                   **extra) -> str:
    """Build initData the way Telegram does (HMAC-SHA256 with key derived from the bot token)."""
    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAH-test", **extra}
    if user is not None:
        fields["user"] = json.dumps(user, separators=(",", ":"))
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


ALICE = {"id": 5001, "first_name": "Alice", "language_code": "ru"}


def auth(init_data: str) -> dict:
    return {"Authorization": f"tma {init_data}"}


@pytest_asyncio.fixture
async def client(session_factory):
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.app = app
        yield c


# ---------- verify_init_data (pure function) ----------

def test_valid_init_data_returns_verified_identity():
    identity = verify_init_data(sign_init_data(ALICE), TOKEN, max_age=3600)
    assert (identity.telegram_id, identity.first_name, identity.language_code) == (5001, "Alice", "ru")


@pytest.mark.parametrize("make, reason", [
    (lambda: "", "missing_or_too_long"),
    (lambda: sign_init_data(ALICE, token="999:OTHER-BOT"), "bad_signature"),
    (lambda: sign_init_data(ALICE).replace("5001", "5002"), "bad_signature"),   # forged user id
    (lambda: sign_init_data(ALICE) + "&extra=1", "bad_signature"),               # added field
    (lambda: sign_init_data(None), "no_user"),
    (lambda: sign_init_data(ALICE, auth_date=int(time.time()) - 7200), "expired"),
    (lambda: sign_init_data(ALICE, auth_date=int(time.time()) + 600), "from_the_future"),
    (lambda: "hash=abc&user=%7B", "bad_signature"),
])
def test_invalid_init_data_is_rejected(make, reason):
    with pytest.raises(InitDataError) as error:
        verify_init_data(make(), TOKEN, max_age=3600)
    assert error.value.reason == reason


def test_signature_field_is_part_of_the_check():
    # Newer clients add a "signature" field; it's covered by the hash like any other field.
    signed = sign_init_data(ALICE, signature="abc123")
    assert verify_init_data(signed, TOKEN, 3600).telegram_id == 5001
    with pytest.raises(InitDataError):
        verify_init_data(signed.replace("abc123", "zzz999"), TOKEN, 3600)


# ---------- HTTP ----------

async def test_health_needs_no_login(client):
    response = await client.get("/api/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer abc"}, {"Authorization": "tma "},
    {"Authorization": "tma user=%7B%22id%22%3A1%7D&hash=deadbeef"},
])
async def test_api_rejects_requests_without_valid_init_data(client, headers):
    for path in ("/api/me", "/api/config"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 401, (path, headers)


async def test_me_creates_user_and_uses_verified_identity(client, session_factory):
    response = await client.get("/api/me", headers=auth(sign_init_data(ALICE)))
    assert response.status_code == 200
    assert response.json() == {
        "first_name": "Alice", "language": None, "language_effective": "ru",
        "disclaimer_accepted": False, "profile_complete": False,
    }
    async with session_factory() as s:
        assert (await users.get_user(s, 5001)) is not None


async def test_client_cannot_choose_its_user_id(client, session_factory):
    # A query parameter or body with another id is simply ignored.
    response = await client.get("/api/me?user_id=1&telegram_id=1",
                                headers=auth(sign_init_data(ALICE)))
    assert response.status_code == 200
    async with session_factory() as s:
        assert await users.get_user(s, 1) is None


async def test_language_is_shared_with_the_bot(client, session_factory):
    headers = auth(sign_init_data(ALICE))
    response = await client.patch("/api/me/language", json={"language": "uz"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["language"] == "uz" and response.json()["language_effective"] == "uz"
    async with session_factory() as s:
        assert (await users.get_user(s, 5001)).language == "uz"   # same field the bot reads

    bad = await client.patch("/api/me/language", json={"language": "de"}, headers=headers)
    assert bad.status_code == 422


async def test_config_returns_attribution_and_languages(client):
    response = await client.get("/api/config", headers=auth(sign_init_data(ALICE)))
    data = response.json()
    assert data["app_name"] == "Gym24" and "RepDB" in data["attribution"]
    assert [lang["code"] for lang in data["languages"]] == ["en", "ru", "uz"]


async def test_rate_limits(client):
    from utils.rate_limit import SlidingWindowLimiter
    client.app.state.user_limiter = SlidingWindowLimiter(3, 60)
    headers = auth(sign_init_data(ALICE))
    codes = [(await client.get("/api/me", headers=headers)).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]

    client.app.state.auth_fail_limiter = SlidingWindowLimiter(2, 60)
    codes = [(await client.get("/api/me")).status_code for _ in range(3)]
    assert codes == [401, 401, 429]


async def test_static_files_and_mini_app_caching(session_factory, tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    (images / "squat-start.webp").write_bytes(b"RIFF....WEBP")
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>Gym24</title>")
    (build / "assets" / "index-abc123.js").write_text("console.log(1)")
    monkeypatch.setattr(api_main, "EXERCISE_IMAGES", images)
    monkeypatch.setattr(api_main, "MINIAPP_BUILD", build)

    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        image = await c.get("/static/exercises/squat-start.webp")
        assert image.status_code == 200 and image.headers["cache-control"] == "public, max-age=604800"
        assert (await c.get("/static/exercises/missing.webp")).status_code == 404

        page = await c.get("/")
        assert "Gym24" in page.text and page.headers["cache-control"] == "no-cache"
        asset = await c.get("/assets/index-abc123.js")
        assert "immutable" in asset.headers["cache-control"]
        deep_link = await c.get("/plan")             # app route on reload -> index.html
        assert deep_link.status_code == 200 and "Gym24" in deep_link.text
        assert (await c.get("/api/does-not-exist")).status_code == 404
