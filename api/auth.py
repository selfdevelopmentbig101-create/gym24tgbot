"""
Telegram Mini App authentication.

The Mini App sends Telegram's signed `initData` string with every request:

    Authorization: tma <initData>

We check its signature with the bot token (HMAC-SHA256, as described in
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
and only then trust the user inside it. The client never sends a user ID on its
own, and the bot token never leaves the server.

Note: Telegram leaves initData EMPTY when a Mini App is opened from a
reply-keyboard button, so the bot opens Gym24 from inline buttons and the menu button.
"""
import time
from dataclasses import dataclass

from aiogram.utils.web_app import check_webapp_signature, parse_webapp_init_data

MAX_INIT_DATA_LENGTH = 8192   # real initData is ~0.5-1 KB
ALLOWED_CLOCK_SKEW = 60       # seconds a client clock may run ahead of ours


class InitDataError(Exception):
    """initData was missing, forged, malformed or too old. `reason` is logged, not shown."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TelegramIdentity:
    """The verified Telegram user. first_name/language_code are used, not stored."""
    telegram_id: int
    first_name: str
    language_code: str | None
    auth_date: int


def verify_init_data(init_data: str, bot_token: str, max_age: int,
                     now: float | None = None) -> TelegramIdentity:
    if not init_data or len(init_data) > MAX_INIT_DATA_LENGTH:
        raise InitDataError("missing_or_too_long")

    # 1. Signature: HMAC-SHA256 over every field except "hash", keyed with the bot token.
    if not check_webapp_signature(bot_token, init_data):
        raise InitDataError("bad_signature")

    # 2. Parse (only after the signature is known to be good).
    try:
        data = parse_webapp_init_data(init_data)
    except Exception:  # noqa: BLE001 - any parsing problem means "don't trust it"
        raise InitDataError("malformed") from None
    if data.user is None:
        raise InitDataError("no_user")

    # 3. Freshness: a leaked initData string must not work forever.
    auth_date = int(data.auth_date.timestamp())
    age = (time.time() if now is None else now) - auth_date
    if age > max_age:
        raise InitDataError("expired")
    if age < -ALLOWED_CLOCK_SKEW:
        raise InitDataError("from_the_future")

    return TelegramIdentity(
        telegram_id=data.user.id,
        first_name=data.user.first_name or "",
        language_code=data.user.language_code,
        auth_date=auth_date,
    )
