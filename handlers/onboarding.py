"""
Onboarding / profile form.

The same 10 steps are used in two modes:
- "onboarding": ask every step in order, then save the whole profile.
- "edit": ask one step, save just that field, show the profile again.

Answers are kept in the FSM (finite state machine) data until saved.
"""
import logging
from enum import Enum

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import Injury
from database.models import Profile
from keyboards.profile import NavCB, ProfileCB, injuries_keyboard, profile_keyboard, step_keyboard
from keyboards.menu import send_main_menu
from services import plans, users
from services.validation import ValidationError
from utils.formatting import format_field_value, format_profile_with_targets
from utils.texts import t

logger = logging.getLogger(__name__)
router = Router(name="onboarding")


class ProfileForm(StatesGroup):
    goal = State()
    age = State()
    sex = State()
    height_cm = State()
    weight_kg = State()
    experience = State()
    training_days = State()
    equipment = State()
    injuries = State()
    diet = State()


STEPS = users.PROFILE_FIELDS  # same order as the questions
TEXT_STEPS = ("age", "height_cm", "weight_kg")  # answered by typing


def state_for(step: str) -> State:
    return getattr(ProfileForm, step)


async def step_from_state(state: FSMContext) -> str | None:
    """'ProfileForm:age' -> 'age'."""
    current = await state.get_state()
    if not current or not current.startswith("ProfileForm:"):
        return None
    return current.split(":", 1)[1]


async def send_or_edit(event: Message | CallbackQuery, text: str,
                       keyboard: InlineKeyboardMarkup | None = None) -> None:
    """After a button tap, edit that message (keeps the chat tidy); otherwise send a new one."""
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=keyboard)
            return
        except TelegramBadRequest:
            pass  # e.g. message too old to edit: just send a new one
        await event.message.answer(text, reply_markup=keyboard)
    else:
        await event.answer(text, reply_markup=keyboard)


async def ask_step(event: Message | CallbackQuery, state: FSMContext, step: str) -> None:
    data = await state.get_data()
    editing = data.get("mode") == "edit"
    index = STEPS.index(step)

    await state.set_state(state_for(step))
    text = t(f"q_{step}")
    if editing:
        text += t("current_value", value=data.get("current", "—"))
    else:
        text = t("step_progress", n=index + 1, total=len(STEPS)) + text

    show_back = editing or index > 0
    await send_or_edit(event, text, step_keyboard(step, show_back, data.get("injuries", [])))


async def start_onboarding(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(mode="onboarding", answers={}, injuries=[])
    await ask_step(event, state, STEPS[0])


async def start_edit(event: Message | CallbackQuery, state: FSMContext,
                     profile: Profile, step: str) -> None:
    current = getattr(profile, step)
    await state.clear()
    await state.update_data(
        mode="edit",
        answers={},
        injuries=list(profile.injuries or []),
        current=format_field_value(step, current),
    )
    await ask_step(event, state, step)


async def show_profile(event: Message | CallbackQuery, profile: Profile, header: str = "",
                       footer: str = "") -> None:
    text = (header + "\n\n" if header else "") + format_profile_with_targets(profile)
    if footer:
        text += "\n\n" + footer
    await send_or_edit(event, text, profile_keyboard())


async def advance(event: Message | CallbackQuery, state: FSMContext,
                  session: AsyncSession, step: str, value) -> None:
    """Store an already-validated answer, then ask the next question or save."""
    if isinstance(value, Enum):
        value = value.value  # keep FSM data JSON-friendly (for Redis storage later)
    data = await state.get_data()
    telegram_id = event.from_user.id

    if data.get("mode") == "edit":
        user = await users.get_user(session, telegram_id)
        await state.clear()
        if user is None or user.profile is None:
            await send_or_edit(event, t("need_profile"))
            return
        old_value = getattr(user.profile, step)
        profile = await users.update_profile_field(session, user, step, value)
        logger.info("Profile field '%s' updated", step)

        footer = ""
        # Equipment, level, days or injuries changed: the old plan no longer fits.
        if step in plans.PLAN_FIELDS and getattr(profile, step) != old_value \
                and await plans.get_plan(session, user) is not None:
            if await plans.generate_for_user(session, user) is not None:
                footer = t("plan_rebuilt")
        await show_profile(event, profile, t("profile_updated"), footer)
        return

    answers = dict(data.get("answers", {}))
    answers[step] = value
    await state.update_data(answers=answers)

    index = STEPS.index(step)
    if index + 1 < len(STEPS):
        await ask_step(event, state, STEPS[index + 1])
        return

    # Last step: save everything in one go, then build the first plan.
    user = await users.get_or_create_user(session, telegram_id)
    profile = await users.save_profile(session, user, answers)
    await state.clear()
    logger.info("Onboarding completed")
    plan = await plans.generate_for_user(session, user)
    footer = (t("plan_ready") + "\n" if plan else "") + t("reminders_hint")
    await show_profile(event, profile, t("onboarding_done"), footer)
    message = event.message if isinstance(event, CallbackQuery) else event
    await send_main_menu(message, t("menu_ready"))


# ---------- Button answers ----------

@router.callback_query(ProfileCB.filter())
async def on_choice(callback: CallbackQuery, callback_data: ProfileCB,
                    state: FSMContext, session: AsyncSession) -> None:
    step, raw = callback_data.field, callback_data.value

    # Ignore buttons from an old question (user scrolled up and tapped).
    if step not in STEPS or await step_from_state(state) != step:
        await callback.answer(t("stale_button"))
        return

    if step == "injuries":
        await on_injury_tap(callback, state, session, raw)
        return

    try:
        value = users.clean_profile_value(step, raw)
    except ValueError:  # ValidationError is a ValueError too
        await callback.answer(t("err_generic"))
        return
    await callback.answer()
    await advance(callback, state, session, step, value)


async def on_injury_tap(callback: CallbackQuery, state: FSMContext,
                        session: AsyncSession, raw: str) -> None:
    """Multi-select: toggle injuries, 'None' clears and continues, 'Done' continues."""
    data = await state.get_data()
    selected: list[str] = list(data.get("injuries", []))

    if raw == "none":
        await callback.answer()
        await advance(callback, state, session, "injuries", [])
        return
    if raw == "done":
        await callback.answer()
        await advance(callback, state, session, "injuries", users.clean_profile_value("injuries", selected))
        return
    if raw not in {i.value for i in Injury}:
        await callback.answer(t("err_generic"))
        return

    if raw in selected:
        selected.remove(raw)
    else:
        selected.append(raw)
    await state.update_data(injuries=selected)
    await callback.answer()

    show_back = data.get("mode") == "edit" or STEPS.index("injuries") > 0
    try:
        await callback.message.edit_reply_markup(reply_markup=injuries_keyboard(selected, show_back))
    except TelegramBadRequest:
        pass  # "message is not modified" after a very fast double tap


@router.callback_query(NavCB.filter(F.action == "back"))
async def on_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    step = await step_from_state(state)
    if step is None:
        await callback.answer(t("stale_button"))
        return
    await callback.answer()

    data = await state.get_data()
    if data.get("mode") == "edit":
        # Back while editing = cancel and return to the profile.
        await state.clear()
        user = await users.get_user(session, callback.from_user.id)
        if user and user.profile:
            await show_profile(callback, user.profile)
        return

    index = STEPS.index(step)
    if index > 0:
        await ask_step(callback, state, STEPS[index - 1])


# ---------- Typed answers ----------

@router.message(StateFilter(*(state_for(s) for s in TEXT_STEPS)), F.text)
async def on_text_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    step = await step_from_state(state)
    try:
        value = users.clean_profile_value(step, message.text)
    except ValidationError as error:
        await message.answer(t(error.text_key))
        return
    await advance(message, state, session, step, value)


@router.message(StateFilter(ProfileForm))
async def on_unexpected_message(message: Message, state: FSMContext) -> None:
    """Text while buttons are expected, or a sticker/photo while a number is expected."""
    step = await step_from_state(state)
    await message.answer(t("err_not_a_number" if step in TEXT_STEPS else "err_use_buttons"))
