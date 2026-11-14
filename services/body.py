"""Body weight and measurements (no Telegram code)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BodyWeightLog, MeasurementLog, User, utcnow
from services import validation

MEASUREMENT_KINDS = ("waist", "chest", "arm", "thigh", "hips")
MEASUREMENT_RANGE_CM = (15.0, 200.0)


def aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; they're stored as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- Body weight ----------

async def log_weight(session: AsyncSession, user: User, value) -> BodyWeightLog:
    """Validate and save a weigh-in. Also updates the profile, so targets follow your weight."""
    kg = validation.validate_weight(value)
    entry = BodyWeightLog(user_id=user.id, weight_kg=kg)
    session.add(entry)
    if user.profile is not None:
        user.profile.weight_kg = kg
    await session.commit()
    return entry


async def last_weight(session: AsyncSession, user: User) -> float | None:
    return await session.scalar(
        select(BodyWeightLog.weight_kg).where(BodyWeightLog.user_id == user.id)
        .order_by(BodyWeightLog.logged_at.desc(), BodyWeightLog.id.desc())
    )


async def weights_since(session: AsyncSession, user: User, since: datetime) -> list[BodyWeightLog]:
    return list(await session.scalars(
        select(BodyWeightLog)
        .where(BodyWeightLog.user_id == user.id, BodyWeightLog.logged_at >= since)
        .order_by(BodyWeightLog.logged_at)
    ))


async def weekly_trend(session: AsyncSession, user: User, now: datetime | None = None) -> float | None:
    """
    Average of the last 7 days minus the average of the 7 days before (kg/week).
    Averages smooth out daily water swings. None until both weeks have data.
    """
    now = now or utcnow()
    entries = await weights_since(session, user, now - timedelta(days=14))
    this_week = [e.weight_kg for e in entries
                 if now - timedelta(days=7) < aware(e.logged_at) <= now]
    last_week = [e.weight_kg for e in entries if aware(e.logged_at) <= now - timedelta(days=7)]
    if not this_week or not last_week:
        return None
    return round(sum(this_week) / len(this_week) - sum(last_week) / len(last_week), 2)


def classify_trend(trend: float, target: tuple[float, float]) -> str:
    """'slow', 'on_track' or 'fast' compared with the goal's healthy weekly gain."""
    low, high = target
    if high == 0:  # recomposition: weight should stay roughly stable
        return "on_track" if abs(trend) <= 0.25 else ("fast" if trend > 0 else "slow")
    if trend < low - 0.05:
        return "slow"
    if trend > high + 0.1:
        return "fast"
    return "on_track"


# ---------- Measurements ----------

def validate_measurement(kind: str, value) -> float:
    if kind not in MEASUREMENT_KINDS:
        raise validation.ValidationError("err_generic")
    try:
        cm = float(str(value).replace(",", ".").lower().replace("cm", "").strip())
    except ValueError:
        raise validation.ValidationError("err_not_a_number") from None
    if not MEASUREMENT_RANGE_CM[0] <= cm <= MEASUREMENT_RANGE_CM[1]:
        raise validation.ValidationError("err_measurement")
    return round(cm, 1)


async def log_measurement(session: AsyncSession, user: User, kind: str, value) -> MeasurementLog:
    entry = MeasurementLog(user_id=user.id, kind=kind, value_cm=validate_measurement(kind, value))
    session.add(entry)
    await session.commit()
    return entry


async def last_measurements(session: AsyncSession, user: User) -> dict[str, float]:
    rows = await session.scalars(
        select(MeasurementLog).where(MeasurementLog.user_id == user.id)
        .order_by(MeasurementLog.logged_at, MeasurementLog.id)
    )
    return {row.kind: row.value_cm for row in rows}  # later rows overwrite earlier ones


async def measurements_since(session: AsyncSession, user: User,
                             since: datetime) -> list[MeasurementLog]:
    return list(await session.scalars(
        select(MeasurementLog)
        .where(MeasurementLog.user_id == user.id, MeasurementLog.logged_at >= since)
        .order_by(MeasurementLog.logged_at)
    ))
