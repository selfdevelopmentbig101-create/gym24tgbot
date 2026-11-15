"""
/api/profile and /api/targets: Mini App onboarding and the daily targets.

Answers are validated by the same code as the bot's onboarding
(services/users.clean_profile_value), and plans are built by the same generator.
"""
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TelegramIdentity
from api.deps import get_identity, get_session, get_user
from api.schemas import GoalOut, ProfileIn, ProfileOut, ProfilePatch, ProfileSaved, TargetsOut
from database.enums import Goal
from database.models import Profile, User
from services import plans, users
from services.nutrition import estimate_goal_date, targets_for_profile
from services.validation import ValidationError
from utils.texts import resolve_language

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["profile"])


def _invalid(field: str, error: str) -> HTTPException:
    """422 with the field and an error key the app translates (e.g. err_age)."""
    return HTTPException(status_code=422, detail={"field": field, "error": error})


def _clean(data: dict) -> dict:
    clean = {}
    for name, value in data.items():
        try:
            clean[name] = users.clean_profile_value(name, value)
        except ValidationError as error:
            raise _invalid(name, error.text_key) from None
        except ValueError:
            raise _invalid(name, "err_generic") from None
    return clean


def _check_target(goal: Goal, weight_kg: float, target: float | None) -> None:
    """A goal weight only makes sense above the current weight, for goals that gain weight."""
    if target is None:
        return
    if goal == Goal.RECOMP or target <= weight_kg:
        raise _invalid("target_weight_kg", "err_target_weight")


def targets_out(profile: Profile, today: date | None = None) -> TargetsOut:
    targets = targets_for_profile(profile)
    goal = estimate_goal_date(profile.weight_kg, profile.target_weight_kg,
                              targets.weekly_gain_kg, today or date.today())
    return TargetsOut(
        calories=targets.calories, protein_g=targets.protein_g, carbs_g=targets.carbs_g,
        fat_g=targets.fat_g, bmr=targets.bmr, tdee=targets.tdee, surplus=targets.surplus,
        protein_g_per_kg=targets.protein_g_per_kg, weekly_gain_kg=targets.weekly_gain_kg,
        goal=GoalOut(**goal.__dict__) if goal else None, notes=targets.notes,
    )


def profile_out(profile: Profile) -> ProfileOut:
    return ProfileOut(**{name: getattr(profile, name) for name in ProfileOut.model_fields})


async def _saved(session: AsyncSession, user: User, rebuilt: bool) -> ProfileSaved:
    return ProfileSaved(profile=profile_out(user.profile), targets=targets_out(user.profile),
                        plan_ready=await plans.get_plan(session, user) is not None,
                        plan_rebuilt=rebuilt)


def _require_profile(user: User) -> Profile:
    if user.profile is None:
        raise HTTPException(status_code=404, detail="no_profile")
    return user.profile


@router.post("/me/disclaimer", status_code=204)
async def accept_disclaimer(user: User = Depends(get_user),
                            session: AsyncSession = Depends(get_session)) -> None:
    """Accept the health disclaimer (same field as the bot's "I understand" button)."""
    if user.disclaimer_accepted_at is None:
        await users.accept_disclaimer(session, user)
        logger.info("Disclaimer accepted in the Mini App")


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: User = Depends(get_user)) -> ProfileOut:
    return profile_out(_require_profile(user))


@router.put("/profile", response_model=ProfileSaved)
async def put_profile(body: ProfileIn, request: Request, background: BackgroundTasks,
                      user: User = Depends(get_user),
                      identity: TelegramIdentity = Depends(get_identity),
                      session: AsyncSession = Depends(get_session)) -> ProfileSaved:
    """Save every onboarding answer. Builds the first workout plan."""
    if user.disclaimer_accepted_at is None:
        raise HTTPException(status_code=409, detail="disclaimer_required")
    clean = _clean(body.model_dump())
    _check_target(clean["goal"], clean["weight_kg"], clean["target_weight_kg"])

    first_time = user.profile is None
    old = {name: getattr(user.profile, name) for name in plans.PLAN_FIELDS} if not first_time else {}
    await users.save_profile(session, user, clean)
    if first_time or await plans.get_plan(session, user) is None:
        rebuilt = await plans.generate_for_user(session, user) is not None
    else:
        changed = {name for name, value in old.items() if getattr(user.profile, name) != value}
        rebuilt = await plans.rebuild_for_profile(session, user, changed)
    logger.info("Profile saved from the Mini App (first time: %s)", first_time)

    if first_time:
        lang = user.language or resolve_language(identity.language_code)
        background.add_task(request.app.state.notifier, identity.telegram_id, lang)
    return await _saved(session, user, rebuilt)


@router.patch("/profile", response_model=ProfileSaved)
async def patch_profile(body: ProfilePatch, user: User = Depends(get_user),
                        session: AsyncSession = Depends(get_session)) -> ProfileSaved:
    """Change some answers. The plan is rebuilt only if equipment, level, days or injuries change."""
    profile = _require_profile(user)
    changes = body.model_dump(exclude_unset=True)
    # Only target_weight_kg may be null (= remove the goal weight).
    for name, value in changes.items():
        if value is None and name != "target_weight_kg":
            raise _invalid(name, "err_generic")
    clean = _clean(changes)
    goal = clean.get("goal", profile.goal)
    weight = clean.get("weight_kg", profile.weight_kg)
    target = clean.get("target_weight_kg", profile.target_weight_kg)
    if "target_weight_kg" in clean:
        _check_target(goal, weight, target)
    elif target is not None and (goal == Goal.RECOMP or target <= weight):
        clean["target_weight_kg"] = None  # the old goal weight no longer applies

    old = {name: getattr(profile, name) for name in plans.PLAN_FIELDS}
    for name, value in clean.items():
        await users.update_profile_field(session, user, name, value)
    changed = {name for name, value in old.items() if getattr(profile, name) != value}
    rebuilt = await plans.get_plan(session, user) is not None \
        and await plans.rebuild_for_profile(session, user, changed)
    logger.info("Profile updated from the Mini App (%s)", ", ".join(sorted(clean)) or "no changes")
    return await _saved(session, user, rebuilt)


@router.get("/targets", response_model=TargetsOut)
async def get_targets(user: User = Depends(get_user)) -> TargetsOut:
    """Daily calories and macros, weekly gain and the estimated goal date."""
    return targets_out(_require_profile(user))
