"""
FastAPI dependencies: database session, verified Telegram identity, current user.

Every /api route except /api/health depends on `get_identity`, so a request
without valid initData never reaches the route.
"""
import logging
from typing import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import InitDataError, TelegramIdentity, verify_init_data
from database.models import User
from services import users

logger = logging.getLogger(__name__)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(status_code=429, detail="rate_limited",
                         headers={"Retry-After": str(retry_after)})


def _reject(request: Request, reason: str) -> HTTPException:
    """401 for bad initData. Repeated failures from one address get 429 instead."""
    ip = _client_ip(request)
    logger.warning("Rejected Mini App request (%s) from %s", reason, ip)
    limiter = request.app.state.auth_fail_limiter
    if not limiter.hit(ip):
        return _too_many(limiter.retry_after(ip))
    return HTTPException(status_code=401, detail="unauthorized",
                         headers={"WWW-Authenticate": "tma"})


async def get_identity(request: Request,
                       authorization: str | None = Header(default=None)) -> TelegramIdentity:
    scheme, _, init_data = (authorization or "").partition(" ")
    if scheme.lower() != "tma" or not init_data:
        raise _reject(request, "no_tma_header")
    state = request.app.state
    try:
        identity = verify_init_data(init_data, state.bot_token, state.init_data_max_age)
    except InitDataError as error:
        raise _reject(request, error.reason) from None

    if not state.user_limiter.hit(identity.telegram_id):
        logger.warning("API rate limit hit")
        raise _too_many(state.user_limiter.retry_after(identity.telegram_id))
    request.state.authenticated = True  # for the request log
    return identity


async def get_user(identity: TelegramIdentity = Depends(get_identity),
                   session: AsyncSession = Depends(get_session)) -> User:
    """The database user for this Telegram account (created on first visit)."""
    return await users.get_or_create_user(session, identity.telegram_id)
