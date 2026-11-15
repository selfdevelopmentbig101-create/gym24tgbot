"""/plan: show the weekly plan, open a day's exercise cards, regenerate."""
import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import WorkoutPlan
from handlers.cards import day_label, format_reps, plan_card, show_card
from handlers.onboarding import send_or_edit
from keyboards.menu import MenuButton
from keyboards.exercises import PlanCB, plan_keyboard
from services import plans, users
from utils.texts import t

router = Router(name="plan")


def format_plan(plan: WorkoutPlan) -> str:
    parts = [t("plan_header", split=t(f"split_{plan.split}"), days=len(plan.days))]
    for day in plan.days:
        lines = [t("plan_day_header", n=day.day_index + 1, name=day_label(day.name_key, day.suffix))]
        for entry in day.exercises:
            lines.append(t("plan_line", name=html.escape(entry.exercise.name),
                           sets=entry.sets, reps=format_reps(entry)))
        parts.append("\n".join(lines))
    parts.append(t("plan_footer"))
    return "\n\n".join(parts)


def plan_markup(plan: WorkoutPlan):
    return plan_keyboard([day_label(d.name_key, d.suffix) for d in plan.days])


async def _load_user(event: Message | CallbackQuery, session: AsyncSession):
    user = await users.get_user(session, event.from_user.id)
    if user is None or user.profile is None:
        if isinstance(event, CallbackQuery):
            await event.answer()
        await send_or_edit(event, t("need_profile"))
        return None
    return user


async def _show_overview(event: Message | CallbackQuery, plan: WorkoutPlan, header: str = "") -> None:
    text = (header + "\n\n" if header else "") + format_plan(plan)
    if isinstance(event, CallbackQuery) and not event.message.text:
        # Coming back from a card with an image: replace it with the text overview.
        await event.message.delete()
        await event.message.answer(text, reply_markup=plan_markup(plan))
        return
    await send_or_edit(event, text, plan_markup(plan))


@router.message(Command("plan"))
@router.message(MenuButton("menu_plan"))
async def cmd_plan(message: Message, session: AsyncSession) -> None:
    user = await _load_user(message, session)
    if user is None:
        return
    plan = await plans.get_or_create_plan(session, user)
    if plan is None:
        await message.answer(t("plan_empty"))
        return
    await _show_overview(message, plan)


@router.callback_query(PlanCB.filter(F.action.in_({"overview", "regen"})))
async def on_overview(callback: CallbackQuery, callback_data: PlanCB, session: AsyncSession) -> None:
    user = await _load_user(callback, session)
    if user is None:
        return
    if callback_data.action == "regen":
        plan, header = await plans.generate_for_user(session, user), t("plan_regenerated")
    else:
        plan, header = await plans.get_or_create_plan(session, user), ""
    await callback.answer()
    if plan is None:
        await send_or_edit(callback, t("plan_empty"))
        return
    await _show_overview(callback, plan, header)


@router.callback_query(PlanCB.filter(F.action == "day"))
async def on_day(callback: CallbackQuery, callback_data: PlanCB, session: AsyncSession) -> None:
    user = await _load_user(callback, session)
    if user is None:
        return
    plan = await plans.get_plan(session, user)
    if plan is None or not 0 <= callback_data.day < len(plan.days) \
            or not plan.days[callback_data.day].exercises:
        await callback.answer(t("plan_changed"), show_alert=True)
        return
    await callback.answer()
    first = plan.days[callback_data.day].exercises[0]
    # Send the first card as a new message so the plan overview stays above it.
    await show_card(callback.message, session, await plan_card(session, first))
