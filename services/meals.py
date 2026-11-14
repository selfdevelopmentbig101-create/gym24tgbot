"""Meal logging and daily totals (no Telegram code)."""
import re
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MealLog, User
from services import reminders
from services.foods import Food, get_food
from services.nutrition import NutritionTargets, targets_for_profile
from services.validation import ValidationError

SERVING_RANGE = (0.25, 10.0)
MAX_ENTRY_KCAL = 3000
MAX_ENTRY_PROTEIN = 300
HISTORY_DAYS = 7  # how far back the summary can be browsed/edited

# "650 40", "650kcal 40g", "chicken wrap 650 40", "2 eggs 145 13"
MANUAL_ENTRY = re.compile(
    r"^\s*(?:(?P<name>.*?)\s+)?(?P<kcal>\d{1,4})\s*(?:kcal|cal)?\s+"
    r"(?P<protein>\d{1,3}(?:[.,]\d)?)\s*(?:g|p|protein)?\s*$",
    re.IGNORECASE,
)


@dataclass
class DaySummary:
    day: date
    kcal: int
    protein_g: float
    entries: list[MealLog]
    targets: NutritionTargets

    @property
    def kcal_left(self) -> int:
        return self.targets.calories - self.kcal

    @property
    def protein_left(self) -> float:
        return self.targets.protein_g - self.protein_g


async def local_today(session: AsyncSession, user: User) -> date:
    """Today in the user's time zone (set in /reminders; UTC otherwise)."""
    return reminders.local_now(await reminders.get_settings(session, user)).date()


def parse_manual(text: str) -> tuple[str | None, int, float]:
    """'chicken wrap 650 40' -> ('chicken wrap', 650, 40.0). Raises ValidationError."""
    match = MANUAL_ENTRY.match(text or "")
    if not match:
        raise ValidationError("err_manual_format")
    name = (match.group("name") or "").strip() or None
    return name, int(match.group("kcal")), float(match.group("protein").replace(",", "."))


def validate_entry(kcal: float, protein: float) -> None:
    if not 1 <= kcal <= MAX_ENTRY_KCAL:
        raise ValidationError("err_meal_kcal")
    if not 0 <= protein <= MAX_ENTRY_PROTEIN:
        raise ValidationError("err_meal_protein_range")
    # Protein has 4 kcal per gram, so it can't add up to more than the total.
    if protein * 4 > kcal + 10:
        raise ValidationError("err_meal_protein")


async def log_food(session: AsyncSession, user: User, food: Food, servings: float = 1) -> MealLog:
    entry = MealLog(user_id=user.id, day=await local_today(session, user), food_id=food.id,
                    name=food.name, servings=1, kcal=food.kcal, protein_g=food.protein_g)
    session.add(entry)
    _apply_servings(entry, food, servings)
    await session.commit()
    return entry


async def log_manual(session: AsyncSession, user: User, name: str | None, kcal: int,
                     protein: float) -> MealLog:
    validate_entry(kcal, protein)
    entry = MealLog(user_id=user.id, day=await local_today(session, user), food_id=None,
                    name=(name or "").strip()[:60] or "Manual entry", servings=1,
                    kcal=int(kcal), protein_g=round(protein, 1))
    session.add(entry)
    await session.commit()
    return entry


def _apply_servings(entry: MealLog, food: Food, servings: float) -> None:
    if not SERVING_RANGE[0] <= servings <= SERVING_RANGE[1]:
        raise ValidationError("err_generic")
    entry.servings = servings
    entry.kcal = round(food.kcal * servings)
    entry.protein_g = round(food.protein_g * servings, 1)


async def get_entry(session: AsyncSession, user: User, entry_id: int) -> MealLog | None:
    entry = await session.get(MealLog, entry_id)
    return entry if entry is not None and entry.user_id == user.id else None


async def set_servings(session: AsyncSession, entry: MealLog, servings: float) -> MealLog:
    """Change servings of a food-list entry (manual entries have no per-serving values)."""
    food = get_food(entry.food_id) if entry.food_id else None
    if food is None:
        raise ValidationError("stale_button")
    _apply_servings(entry, food, servings)
    await session.commit()
    return entry


async def delete_entry(session: AsyncSession, entry: MealLog) -> None:
    await session.delete(entry)
    await session.commit()


async def day_summary(session: AsyncSession, user: User, day: date) -> DaySummary:
    entries = list(await session.scalars(
        select(MealLog).where(MealLog.user_id == user.id, MealLog.day == day)
        .order_by(MealLog.logged_at, MealLog.id)
    ))
    return DaySummary(day, sum(e.kcal for e in entries), round(sum(e.protein_g for e in entries), 1),
                      entries, targets_for_profile(user.profile))


async def week_average(session: AsyncSession, user: User, today: date) -> tuple[int, int, int] | None:
    """(avg kcal, avg protein, days) over the last 7 days before today that have entries."""
    rows = await session.scalars(
        select(MealLog).where(MealLog.user_id == user.id, MealLog.day >= today - timedelta(days=7),
                              MealLog.day < today)
    )
    per_day: dict[date, list[float]] = {}
    for row in rows:
        totals = per_day.setdefault(row.day, [0, 0])
        totals[0] += row.kcal
        totals[1] += row.protein_g
    if not per_day:
        return None
    days = len(per_day)
    return (round(sum(v[0] for v in per_day.values()) / days),
            round(sum(v[1] for v in per_day.values()) / days), days)


async def recent_foods(session: AsyncSession, user: User, diet, limit: int = 6) -> list[Food]:
    """Foods from the list logged in the last 30 days, most recent first."""
    from services.foods import allowed

    today = await local_today(session, user)
    rows = await session.scalars(
        select(MealLog.food_id).where(MealLog.user_id == user.id, MealLog.food_id.is_not(None),
                                      MealLog.day >= today - timedelta(days=30))
        .order_by(MealLog.logged_at.desc(), MealLog.id.desc())
    )
    result: list[Food] = []
    for food_id in rows:
        food = get_food(food_id)
        if food and food not in result and allowed(food, diet):
            result.append(food)
        if len(result) >= limit:
            break
    return result
