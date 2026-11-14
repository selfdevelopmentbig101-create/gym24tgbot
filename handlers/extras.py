"""
/achievements, streak lines, and the Accept / Not now buttons for
auto-adjust suggestions (deload week, calorie changes).
"""
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.onboarding import send_or_edit
from keyboards.extras import AdjCB, calories_keyboard, deload_keyboard
from services import achievements, adjust, users
from services.achievements import ACHIEVEMENTS, AchievementDef, Stats
from utils.texts import t

router = Router(name="extras")


# ---------- Text helpers used by other handlers ----------

def achievement_name(a: AchievementDef) -> str:
    return f"{a.emoji} {t(f'ach_{a.code}')}"


def new_achievements_text(new: list[AchievementDef]) -> str:
    if not new:
        return ""
    return t("ach_unlocked", names=", ".join(achievement_name(a) for a in new))


def streak_text(stats: Stats) -> str:
    if stats.week_streak == 0 and stats.week_done == 0:
        return ""
    return t("streak_line", weeks=stats.week_streak, done=stats.week_done, goal=stats.week_goal)


def deload_offer(stalled) -> tuple[str, object]:
    names = ", ".join(html.escape(e.name) for e in stalled[:4])
    return t("deload_offer", names=names), deload_keyboard()


def calorie_offer(suggestion: adjust.CalorieSuggestion) -> tuple[str, object]:
    key = "kcal_offer_up" if suggestion.delta > 0 else "kcal_offer_down"
    text = t(key, trend=f"{suggestion.trend:+.2f}", kcal=abs(suggestion.delta),
             new=suggestion.new_calories)
    return text, calories_keyboard(suggestion.delta)


async def send_suggestions(target: Message, session: AsyncSession, user,
                           deload: bool = True, calories: bool = True) -> None:
    """Send pending auto-adjust suggestions, each as its own message with buttons."""
    if deload:
        stalled = await adjust.deload_suggestion(session, user)
        if stalled:
            text, keyboard = deload_offer(stalled)
            await target.answer(text, reply_markup=keyboard)
    if calories:
        suggestion = await adjust.calorie_suggestion(session, user)
        if suggestion:
            text, keyboard = calorie_offer(suggestion)
            await target.answer(text, reply_markup=keyboard)


# ---------- /achievements ----------

def _progress(value: float, threshold: float) -> str:
    return f"{min(value, threshold):g}/{threshold:g}"


@router.message(Command("achievements"))
async def cmd_achievements(message: Message, session: AsyncSession) -> None:
    user = await users.get_user(session, message.from_user.id)
    if user is None or user.profile is None:
        await message.answer(t("need_profile"))
        return
    await achievements.check_new(session, user)
    stats = await achievements.compute_stats(session, user)
    have = await achievements.unlocked(session, user)

    lines = [t("ach_header", n=len(have), total=len(ACHIEVEMENTS))]
    streak = streak_text(stats)
    if streak:
        lines.append(streak)
    if stats.protein_streak:
        lines.append(t("protein_streak_line", days=stats.protein_streak))
    lines.append("")
    for a in ACHIEVEMENTS:
        if a.code in have:
            when = have[a.code].unlocked_at.strftime("%d %b %Y")
            lines.append(t("ach_line_done", name=achievement_name(a), date=when))
        else:
            lines.append(t("ach_line_locked", name=t(f"ach_{a.code}"),
                           desc=t(f"ach_{a.code}_desc"),
                           progress=_progress(stats.value(a.stat), a.threshold)))
    await message.answer("\n".join(lines))


# ---------- Accept / Not now ----------

@router.callback_query(AdjCB.filter())
async def on_adjust(callback: CallbackQuery, callback_data: AdjCB, session: AsyncSession) -> None:
    user = await users.get_user(session, callback.from_user.id)
    if user is None or user.profile is None:
        await callback.answer(t("need_profile"), show_alert=True)
        return
    action = callback_data.a
    if action == "deload_yes":
        until = await adjust.start_deload(session, user)
        text = t("deload_started", until=until.strftime("%d %b"))
    elif action == "deload_no":
        await adjust.dismiss_deload(session, user)
        text = t("adjust_dismissed")
    elif action == "kcal_yes":
        try:
            calories = await adjust.apply_calories(session, user, callback_data.v)
        except ValueError:
            await callback.answer(t("stale_button"))
            return
        text = t("kcal_applied", calories=calories)
    elif action == "kcal_no":
        await adjust.dismiss_calories(session, user)
        text = t("adjust_dismissed")
    else:
        await callback.answer(t("stale_button"))
        return
    await callback.answer()
    await send_or_edit(callback, text)


