"""Telegram handlers. Routers are included in this order, so commands work
even in the middle of onboarding."""
from aiogram import Router

from handlers import (admin, cards, common, extras, food, library, onboarding, plan, profile,
                      progress, reminders, workout)


def get_routers() -> list[Router]:
    return [admin.router, common.router, profile.router, progress.router, reminders.router,
            extras.router, workout.router,
            food.router, plan.router, library.router, cards.router,
            onboarding.router]
