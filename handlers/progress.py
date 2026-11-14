"""/progress, /weight, /measure: body weight, measurements, PRs and charts."""
import asyncio
import html
from collections import defaultdict
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, SetLog, User, WorkoutSession, utcnow
from handlers.onboarding import send_or_edit
from keyboards.progress import (
    ProgCB,
    back_to_progress,
    chart_keyboard,
    measure_keyboard,
    measure_kinds_keyboard,
    progress_keyboard,
    strength_keyboard,
    weight_keyboard,
)
from handlers import extras
from handlers.premium import send_locked
from services import achievements, body, charts, premium, records, reminders, users
from services.body import aware
from services.nutrition import targets_for_profile
from services.validation import ValidationError
from utils.texts import t

router = Router(name="progress")


class ProgressForm(StatesGroup):
    weight = State()   # waiting for a typed body weight
    measure = State()  # waiting for a typed measurement (kind in FSM data)


async def _user(event, session: AsyncSession) -> User | None:
    user = await users.get_user(session, event.from_user.id)
    if user is None or user.profile is None:
        if isinstance(event, CallbackQuery):
            await event.answer()
        await send_or_edit(event, t("need_profile"))
        return None
    return user


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")




# ---------- Summary ----------

async def progress_text(session: AsyncSession, user: User) -> str:
    now = utcnow()
    lines = [t("progress_header"), ""]

    week = await body.weights_since(session, user, now - timedelta(days=7))
    last = await body.last_weight(session, user)
    if last is None:
        lines.append(t("progress_no_weight"))
    else:
        avg = t("progress_weight_avg", avg=_fmt(sum(w.weight_kg for w in week) / len(week))) \
            if len(week) >= 2 else ""
        lines.append(t("progress_weight", weight=_fmt(last), avg=avg))
        lines.append(trend_line(await body.weekly_trend(session, user, now), user))

    counts = []
    for days in (7, 30):
        counts.append(await session.scalar(
            select(func.count()).select_from(WorkoutSession)
            .where(WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_not(None),
                   WorkoutSession.finished_at >= now - timedelta(days=days))) or 0)
    lines.append(t("progress_workouts", week=counts[0], month=counts[1]))
    stats = await achievements.compute_stats(session, user)
    streak = extras.streak_text(stats)
    if streak:
        lines.append(streak)
    unlocked = await achievements.unlocked(session, user)
    lines.append(t("progress_achievements", n=len(unlocked), total=len(achievements.ACHIEVEMENTS)))

    measurements = await body.last_measurements(session, user)
    if measurements:
        values = ", ".join(f"{t('measure_' + k)} {_fmt(v)} cm" for k, v in measurements.items())
        lines.append(t("progress_measurements", values=values))

    prs = (await records.personal_records(session, user))[:3]
    if prs:
        lines += ["", t("progress_top_prs")]
        lines += [t("progress_pr_line", name=html.escape(r.exercise.name), e1rm=_fmt(r.best_e1rm),
                    weight=_fmt(r.best_weight), reps=r.best_reps) for r in prs]
    return "\n".join(lines)


def trend_line(trend: float | None, user: User) -> str:
    if trend is None:
        return t("progress_trend_wait")
    low, high = targets_for_profile(user.profile).weekly_gain_kg
    verdict = body.classify_trend(trend, (low, high))
    if high == 0 and verdict != "on_track":
        text = t("trend_recomp_off")
    else:
        text = t(f"trend_{verdict}", low=low, high=high)
    return t("progress_trend", trend=f"{trend:+.2f}", verdict=text)


async def _show_progress(event, session: AsyncSession, user: User) -> None:
    text = await progress_text(session, user)
    if isinstance(event, CallbackQuery) and not event.message.text:
        # Coming back from a chart (a photo): send the summary as a new message.
        await event.message.answer(text, reply_markup=progress_keyboard())
    else:
        await send_or_edit(event, text, progress_keyboard())
    target = event.message if isinstance(event, CallbackQuery) else event
    await extras.send_suggestions(target, session, user)


@router.message(Command("progress"))
async def cmd_progress(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(message, session)
    if user:
        await state.clear()
        await _show_progress(message, session, user)


@router.callback_query(ProgCB.filter(F.a == "menu"))
async def on_menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(callback, session)
    if user:
        await state.clear()
        await callback.answer()
        await _show_progress(callback, session, user)


# ---------- Body weight ----------

async def _save_weight(event, session: AsyncSession, user: User, value) -> None:
    before = targets_for_profile(user.profile)
    entry = await body.log_weight(session, user, value)
    after = targets_for_profile(user.profile)
    lines = [t("weight_logged", weight=_fmt(entry.weight_kg)),
             trend_line(await body.weekly_trend(session, user), user)]
    if (before.calories, before.protein_g) != (after.calories, after.protein_g):
        lines.append(t("targets_updated", calories=after.calories, protein=after.protein_g))
    new = await achievements.check_new(session, user)
    if new:
        lines.append(extras.new_achievements_text(new))
    await send_or_edit(event, "\n\n".join(lines), back_to_progress())
    target = event.message if isinstance(event, CallbackQuery) else event
    await extras.send_suggestions(target, session, user, deload=False)


async def _show_weight_logger(event, session: AsyncSession, user: User, state: FSMContext) -> None:
    start = await body.last_weight(session, user) or user.profile.weight_kg
    await state.set_state(ProgressForm.weight)  # typing a number also works
    await send_or_edit(event, t("weight_prompt"), weight_keyboard(start))


@router.message(Command("weight"))
async def cmd_weight(message: Message, command: CommandObject, session: AsyncSession,
                     state: FSMContext) -> None:
    user = await _user(message, session)
    if user is None:
        return
    if command.args:  # "/weight 75.4" logs straight away
        try:
            await _save_weight(message, session, user, command.args)
        except ValidationError as error:
            await message.answer(t(error.text_key))
        return
    await _show_weight_logger(message, session, user, state)


@router.callback_query(ProgCB.filter(F.a.in_({"wlog", "wset", "wsave"})))
async def on_weight(callback: CallbackQuery, callback_data: ProgCB, session: AsyncSession,
                    state: FSMContext) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    if callback_data.a == "wlog":
        await callback.answer()
        await _show_weight_logger(callback, session, user, state)
        return
    if callback_data.a == "wset":
        await callback.answer()
        try:
            await callback.message.edit_reply_markup(reply_markup=weight_keyboard(float(callback_data.v)))
        except TelegramBadRequest:
            pass
        return
    try:
        await state.clear()
        await callback.answer()
        await _save_weight(callback, session, user, callback_data.v)
    except ValidationError as error:
        await callback.answer(t(error.text_key), show_alert=True)


@router.message(ProgressForm.weight, F.text)
async def on_typed_weight(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(message, session)
    if user is None:
        return
    try:
        await _save_weight(message, session, user, message.text)
    except ValidationError as error:
        await message.answer(t(error.text_key))
        return
    await state.clear()


# ---------- Measurements ----------

@router.message(Command("measure"))
async def cmd_measure(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if await _user(message, session):
        await state.clear()
        await message.answer(t("measure_pick"), reply_markup=measure_kinds_keyboard())


@router.callback_query(ProgCB.filter(F.a.in_({"mlog", "mkind", "mset", "msave"})))
async def on_measure(callback: CallbackQuery, callback_data: ProgCB, session: AsyncSession,
                     state: FSMContext) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    action = callback_data.a
    if action == "mlog":
        await callback.answer()
        await state.clear()
        await send_or_edit(callback, t("measure_pick"), measure_kinds_keyboard())
        return

    kind, _, value = callback_data.v.partition("|")
    if kind not in body.MEASUREMENT_KINDS:
        await callback.answer(t("stale_button"))
        return
    label = t(f"measure_{kind}")

    if action == "mkind":
        await callback.answer()
        await state.set_state(ProgressForm.measure)
        await state.update_data(kind=kind)
        last = (await body.last_measurements(session, user)).get(kind)
        if last is None:
            await send_or_edit(callback, t("measure_prompt_first", kind=label), back_to_progress())
        else:
            await send_or_edit(callback, t("measure_prompt", kind=label), measure_keyboard(kind, last))
        return
    if action == "mset":
        await callback.answer()
        try:
            await callback.message.edit_reply_markup(reply_markup=measure_keyboard(kind, float(value)))
        except TelegramBadRequest:
            pass
        return
    try:
        entry = await body.log_measurement(session, user, kind, value)
    except ValidationError as error:
        await callback.answer(t(error.text_key), show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await send_or_edit(callback, t("measure_logged", kind=label, value=_fmt(entry.value_cm)),
                       back_to_progress())


@router.message(ProgressForm.measure, F.text)
async def on_typed_measure(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _user(message, session)
    if user is None:
        return
    kind = (await state.get_data()).get("kind")
    try:
        entry = await body.log_measurement(session, user, kind, message.text)
    except ValidationError as error:
        await message.answer(t(error.text_key))
        return
    await state.clear()
    await message.answer(t("measure_logged", kind=t(f"measure_{kind}"), value=_fmt(entry.value_cm)),
                         reply_markup=back_to_progress())


# ---------- PRs ----------

@router.callback_query(ProgCB.filter(F.a == "prs"))
async def on_prs(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    prs = await records.personal_records(session, user)
    if not prs:
        text = t("prs_none")
    else:
        text = "\n".join([t("prs_header"), ""] + [
            t("prs_line", name=html.escape(r.exercise.name), e1rm=_fmt(r.best_e1rm),
              weight=_fmt(r.best_weight), reps=r.best_reps, heaviest=_fmt(r.heaviest_kg))
            for r in prs[:25]])
    await callback.answer()
    await send_or_edit(callback, text, back_to_progress())


# ---------- Charts ----------

async def build_chart(session: AsyncSession, user: User, chart: str, days: int) -> bytes | None:
    """PNG bytes for a chart, or None if there's not enough data."""
    since = utcnow() - timedelta(days=days)
    settings = await reminders.get_settings(session, user)

    def local(dt) -> date:
        """Calendar date in the user's time zone (UTC until reminders are set up)."""
        return reminders.local_now(settings, aware(dt)).date()

    if chart == "weight":
        entries = await body.weights_since(session, user, since)
        if len(entries) < 2:
            return None
        xs = [local(e.logged_at) for e in entries]
        return await asyncio.to_thread(
            charts.line_chart, t("chart_weight_title", days=days), "kg",
            [("Weigh-ins", xs, [e.weight_kg for e in entries])], True)

    if chart == "volume":
        sets = await session.scalars(
            select(SetLog).where(SetLog.user_id == user.id, SetLog.created_at >= since))
        per_day: dict[date, float] = defaultdict(float)
        for s in sets:
            per_day[local(s.created_at)] += s.weight_kg * s.reps
        if not per_day:
            return None
        today = local(utcnow())
        xs = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        return await asyncio.to_thread(
            charts.bar_chart, t("chart_volume_title", days=days), "kg × reps",
            xs, [per_day.get(x, 0) for x in xs])

    if chart == "measure":
        entries = await body.measurements_since(session, user, since)
        series: dict[str, tuple[list, list]] = {}
        for e in entries:
            xs, ys = series.setdefault(e.kind, ([], []))
            xs.append(local(e.logged_at))
            ys.append(e.value_cm)
        lines = [(t(f"measure_{k}"), xs, ys) for k, (xs, ys) in series.items() if len(xs) >= 2]
        if not lines:
            return None
        return await asyncio.to_thread(charts.line_chart, t("chart_measure_title", days=days),
                                       "cm", lines)

    if chart.startswith("s."):  # "s.<exercise id>" (":" is reserved in callback data)
        exercise = await session.get(Exercise, chart[2:])
        if exercise is None:
            return None
        history = await records.e1rm_history(session, user, exercise.id, since)
        if len(history) < 2:
            return None
        xs = [local(when) for when, _ in history]
        return await asyncio.to_thread(
            charts.line_chart, t("chart_strength_title", name=exercise.name, days=days), "kg",
            [("Estimated 1RM", xs, [round(v, 1) for _, v in history])])
    return None


@router.callback_query(ProgCB.filter(F.a == "strength"))
async def on_strength(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    if not premium.has(user, "charts"):
        await send_locked(callback)
        return
    exercises = await records.logged_exercises(session, user)
    await callback.answer()
    if not exercises:
        await send_or_edit(callback, t("strength_none"), back_to_progress())
        return
    await send_or_edit(callback, t("strength_pick"), strength_keyboard(exercises))


@router.callback_query(ProgCB.filter(F.a == "chart"))
async def on_chart(callback: CallbackQuery, callback_data: ProgCB, session: AsyncSession) -> None:
    user = await _user(callback, session)
    if user is None:
        return
    if not premium.has(user, "charts"):
        await send_locked(callback)
        return
    days = callback_data.r if callback_data.r in (7, 30) else 30
    try:
        png = await build_chart(session, user, callback_data.v, days)
    except charts.ChartsUnavailable:
        await callback.answer(t("charts_unavailable"), show_alert=True)
        return
    if png is None:
        await callback.answer(t("chart_no_data"), show_alert=True)
        return
    await callback.answer()
    photo = BufferedInputFile(png, filename="chart.png")
    keyboard = chart_keyboard(callback_data.v, days)
    if callback.message.photo:
        # Switching week/month on an existing chart: replace the image in place.
        await callback.message.edit_media(InputMediaPhoto(media=photo), reply_markup=keyboard)
    else:
        await callback.message.answer_photo(photo, reply_markup=keyboard)
