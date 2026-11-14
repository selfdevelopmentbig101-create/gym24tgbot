"""Telegram handlers. Routers are included in this order, so commands work
even in the middle of onboarding."""
from aiogram import Router

from handlers import common, onboarding, profile


def get_routers() -> list[Router]:
    return [common.router, profile.router, onboarding.router]
