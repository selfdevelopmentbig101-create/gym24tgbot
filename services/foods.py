"""
The quick-log food list (data/foods.json): loading, validation, diet filter.
No database: the list is small and read-only, so it's cached in memory.
"""
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from database.enums import Diet

FOODS_FILE = Path(__file__).resolve().parent.parent / "data" / "foods.json"
CATEGORIES = ("protein", "carbs", "fruit_veg", "snacks", "meals")
# What each food contains, from most to least restrictive.
DIET_LEVELS = ("vegan", "vegetarian", "pescatarian", "meat")
# Highest food level each diet preference allows.
ALLOWED_LEVEL = {Diet.VEGAN: 0, Diet.VEGETARIAN: 1, Diet.PESCATARIAN: 2, Diet.NONE: 3}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class FoodDataError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s) in foods.json:\n- " + "\n- ".join(problems))


@dataclass(frozen=True)
class Food:
    id: str
    name: str
    serving: str
    kcal: int
    protein_g: float
    category: str
    diet: str


def validate_foods(raw: object) -> list[Food]:
    entries = raw.get("foods") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        raise FoodDataError(['The file must be an object with a "foods" list.'])
    problems, foods, seen = [], [], set()
    for index, entry in enumerate(entries):
        where = f"food #{index + 1}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be an object")
            continue
        food_id = entry.get("id")
        if isinstance(food_id, str):
            where = f"'{food_id}'"
        if not isinstance(food_id, str) or not ID_PATTERN.match(food_id) or len(food_id) > 30:
            problems.append(f"{where}: id must be lowercase-with-dashes, max 30 chars")
        elif food_id in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(food_id)
        for field in ("name", "serving"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                problems.append(f"{where}: '{field}' must be non-empty text")
        kcal, protein = entry.get("kcal"), entry.get("protein_g")
        if not isinstance(kcal, (int, float)) or not 0 <= kcal <= 2000:
            problems.append(f"{where}: kcal must be a number between 0 and 2000")
        if not isinstance(protein, (int, float)) or protein < 0:
            problems.append(f"{where}: protein_g must be a number >= 0")
        elif isinstance(kcal, (int, float)) and protein * 4 > kcal + 10:
            problems.append(f"{where}: protein ({protein} g = {protein * 4} kcal) exceeds total kcal")
        if entry.get("category") not in CATEGORIES:
            problems.append(f"{where}: category must be one of {CATEGORIES}")
        if entry.get("diet") not in DIET_LEVELS:
            problems.append(f"{where}: diet must be one of {DIET_LEVELS}")
        if not problems or not any(p.startswith(where) for p in problems):
            foods.append(Food(food_id, entry["name"].strip(), entry["serving"].strip(),
                              int(round(kcal)), float(protein), entry["category"], entry["diet"]))
    if problems:
        raise FoodDataError(problems)
    return foods


@lru_cache(maxsize=1)
def all_foods() -> tuple[Food, ...]:
    try:
        raw = json.loads(FOODS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FoodDataError([f"File not found: {FOODS_FILE}"]) from None
    except json.JSONDecodeError as error:
        raise FoodDataError([f"Invalid JSON: {error}"]) from None
    return tuple(validate_foods(raw))


def get_food(food_id: str) -> Food | None:
    return next((f for f in all_foods() if f.id == food_id), None)


def allowed(food: Food, diet) -> bool:
    return DIET_LEVELS.index(food.diet) <= ALLOWED_LEVEL[Diet(diet)]


def foods_for(diet, category: str | None = None) -> list[Food]:
    """Foods that fit the diet preference, in file order."""
    return [f for f in all_foods() if allowed(f, diet) and (category is None or f.category == category)]


def protein_ideas(diet, limit: int = 3) -> list[Food]:
    """High-protein, low-calorie options for a 'protein left to hit' hint."""
    options = [f for f in foods_for(diet) if f.protein_g >= 15 and f.kcal > 0]
    return sorted(options, key=lambda f: f.protein_g * 4 / f.kcal, reverse=True)[:limit]
