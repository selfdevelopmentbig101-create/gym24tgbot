"""
Premium (no Telegram code). Paid with Telegram Stars.

Free: everything needed to train and eat right (plans, logging, rest timer,
overload hints, PRs, food, reminders, achievements, Mini App logger).
Premium: the "extra insight" features listed in PREMIUM_FEATURES.
Admins always have Premium; PREMIUM_ENABLED=false makes everything free.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import Payment, User, utcnow
from services.body import aware

PREMIUM_FEATURES = ("charts", "suggestions", "app_progress")
TRIAL_DAYS = 7


@dataclass(frozen=True)
class Plan:
    code: str
    days: int
    stars: int


def plans() -> dict[str, Plan]:
    return {
        "month": Plan("month", 30, config.premium_month_stars),
        "year": Plan("year", 365, config.premium_year_stars),
    }


def is_premium(user: User | None, now: datetime | None = None) -> bool:
    if not config.premium_enabled:
        return True
    if user is None:
        return False
    if user.telegram_id in config.admin_ids:
        return True
    return user.premium_until is not None and aware(user.premium_until) > (now or utcnow())


def has(user: User | None, feature: str) -> bool:
    return feature not in PREMIUM_FEATURES or is_premium(user)


async def _extend(session: AsyncSession, user: User, days: int) -> datetime:
    """Add days on top of any remaining Premium time."""
    now = utcnow()
    start = aware(user.premium_until) if user.premium_until and aware(user.premium_until) > now else now
    user.premium_until = start + timedelta(days=days)
    await session.commit()
    return user.premium_until


async def start_trial(session: AsyncSession, user: User) -> datetime | None:
    """One free trial per user. Returns the end date, or None if already used."""
    if user.trial_used:
        return None
    user.trial_used = True
    return await _extend(session, user, TRIAL_DAYS)


# ---------- Payments ----------

def make_payload(plan: str, user_id: int) -> str:
    return f"premium:{plan}:{user_id}"


def parse_payload(payload: str) -> tuple[Plan, int] | None:
    parts = (payload or "").split(":")
    if len(parts) != 3 or parts[0] != "premium" or parts[1] not in plans() or not parts[2].isdigit():
        return None
    return plans()[parts[1]], int(parts[2])


def check_checkout(payload: str, user_id: int, currency: str, amount: int) -> bool:
    """Validate a pre-checkout query: our payload, this user, current price in Stars."""
    parsed = parse_payload(payload)
    return (parsed is not None and parsed[1] == user_id and currency == "XTR"
            and amount == parsed[0].stars)


async def record_payment(session: AsyncSession, user: User, plan: Plan, charge_id: str,
                         stars: int) -> datetime:
    """Save the payment and extend Premium. Safe to call twice for the same charge."""
    existing = await session.scalar(select(Payment).where(Payment.charge_id == charge_id))
    if existing is not None:
        return user.premium_until
    session.add(Payment(user_id=user.id, plan=plan.code, stars=stars, days=plan.days,
                        charge_id=charge_id))
    return await _extend(session, user, plan.days)


async def mark_refunded(session: AsyncSession, payment: Payment, user: User) -> None:
    """After Telegram confirmed the refund: remove the days that payment added."""
    payment.refunded = True
    if user.premium_until is not None:
        until = aware(user.premium_until) - timedelta(days=payment.days)
        user.premium_until = max(until, utcnow())
    await session.commit()
