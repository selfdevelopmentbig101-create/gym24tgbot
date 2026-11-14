"""Telegram handlers. Routers are included in this order, so commands work
even in the middle of onboarding."""
from aiogram import Router

from handlers import cards, common, library, onboarding, plan, profile, workout


def get_routers() -> list[Router]:
    return [common.router, profile.router, workout.router, plan.router, library.router, cards.router,
            onboarding.router]
