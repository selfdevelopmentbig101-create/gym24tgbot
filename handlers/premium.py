"""
/premium and Telegram Stars payments.

Flow: /premium -> plan button -> Telegram invoice (in Stars) -> the user pays
in Telegram -> pre_checkout_query (we validate) -> successful_payment message
(we save it and extend Premium). /paysupport is required by Telegram's terms
for bots that sell digital goods.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import User
from handlers.onboarding import send_or_edit
from services import premium, users
from services.body import aware
from utils.texts import fmt_day, t

logger = logging.getLogger(__name__)
router = Router(name="premium")


class PremCB(CallbackData, prefix="pr"):
    a: str        # menu | buy | trial
    v: str = ""   # plan code


def premium_keyboard(user: User | None):
    b = InlineKeyboardBuilder()
    month, year = premium.plans()["month"], premium.plans()["year"]
    b.button(text=t("btn_premium_month", stars=month.stars), callback_data=PremCB(a="buy", v="month"))
    saving = round(100 - year.stars / (month.stars * 12) * 100)
    b.button(text=t("btn_premium_year", stars=year.stars, saving=saving),
             callback_data=PremCB(a="buy", v="year"))
    if user is not None and not user.trial_used and not premium.is_premium(user):
        b.button(text=t("btn_premium_trial", days=premium.TRIAL_DAYS), callback_data=PremCB(a="trial"))
    b.adjust(1)
    return b.as_markup()


def offer_keyboard():
    """A single 'See Premium' button for locked features."""
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_see_premium"), callback_data=PremCB(a="menu"))
    return b.as_markup()


def premium_text(user: User | None) -> str:
    lines = [t("premium_header"), "", t("premium_free"), "", t("premium_features"), ""]
    if not config.premium_enabled:
        lines.append(t("premium_all_free"))
    elif premium.is_premium(user):
        until = user.premium_until
        if user.telegram_id in config.admin_ids or until is None:
            lines.append(t("premium_active_forever"))
        else:
            lines.append(t("premium_active", until=fmt_day(aware(until).date(), with_year=True)))
    else:
        lines.append(t("premium_inactive"))
    return "\n".join(lines)


async def send_locked(callback: CallbackQuery) -> None:
    """Tell the user a feature is Premium, with a button to see the offer."""
    await callback.answer(t("premium_required"), show_alert=True)
    await callback.message.answer(t("premium_locked"), reply_markup=offer_keyboard())


@router.message(Command("premium"))
async def cmd_premium(message: Message, session: AsyncSession) -> None:
    user = await users.get_user(session, message.from_user.id)
    keyboard = premium_keyboard(user) if config.premium_enabled else None
    await message.answer(premium_text(user), reply_markup=keyboard)


@router.callback_query(PremCB.filter(F.a == "menu"))
async def on_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await users.get_user(session, callback.from_user.id)
    await callback.answer()
    keyboard = premium_keyboard(user) if config.premium_enabled else None
    await send_or_edit(callback, premium_text(user), keyboard)


@router.callback_query(PremCB.filter(F.a == "trial"))
async def on_trial(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await users.get_or_create_user(session, callback.from_user.id)
    until = await premium.start_trial(session, user)
    if until is None:
        await callback.answer(t("premium_trial_used"), show_alert=True)
        return
    logger.info("Premium trial started")
    await callback.answer()
    await send_or_edit(callback, t("premium_trial_started", days=premium.TRIAL_DAYS,
                                   until=fmt_day(aware(until).date())))


@router.callback_query(PremCB.filter(F.a == "buy"))
async def on_buy(callback: CallbackQuery, callback_data: PremCB, bot: Bot,
                 session: AsyncSession) -> None:
    plan = premium.plans().get(callback_data.v)
    if plan is None or not config.premium_enabled:
        await callback.answer(t("stale_button"))
        return
    await callback.answer()
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=t(f"premium_invoice_title_{plan.code}"),
        description=t("premium_invoice_desc", days=plan.days),
        payload=premium.make_payload(plan.code, callback.from_user.id),
        currency="XTR",  # Telegram Stars: no provider token needed
        prices=[LabeledPrice(label=t(f"premium_invoice_title_{plan.code}"), amount=plan.stars)],
    )


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    ok = premium.check_checkout(query.invoice_payload, query.from_user.id, query.currency,
                                query.total_amount)
    if ok:
        await query.answer(ok=True)
    else:
        logger.warning("Rejected a pre-checkout query (stale price or wrong user)")
        await query.answer(ok=False, error_message=t("premium_checkout_error"))


@router.message(F.successful_payment)
async def on_paid(message: Message, session: AsyncSession) -> None:
    payment = message.successful_payment
    parsed = premium.parse_payload(payment.invoice_payload)
    if parsed is None:
        logger.error("Payment with an unknown payload received")
        return
    plan, _ = parsed
    user = await users.get_or_create_user(session, message.from_user.id)
    until = await premium.record_payment(session, user, plan, payment.telegram_payment_charge_id,
                                         payment.total_amount)
    logger.info("Premium purchased (%s, %s Stars)", plan.code, payment.total_amount)
    await message.answer(t("premium_thanks", until=fmt_day(aware(until).date(), with_year=True),
                           charge=payment.telegram_payment_charge_id))


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message) -> None:
    await message.answer(t("paysupport"))
