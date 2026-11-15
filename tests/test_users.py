import pytest
from sqlalchemy import func, select

from database.models import Exercise, Profile, User
from services import users
from services.validation import ValidationError

VALID = {
    "goal": "lean_bulk", "age": 27, "sex": "male", "height_cm": 180, "weight_kg": 75,
    "experience": "beginner", "training_days": 3, "equipment": "full_gym",
    "injuries": ["knee", "knee", "shoulder"], "diet": "none",
}


async def test_save_and_update_profile(session_factory):
    async with session_factory() as session:
        user = await users.get_or_create_user(session, 111)
        profile = await users.save_profile(session, user, VALID)
        assert profile.injuries == ["knee", "shoulder"]  # de-duplicated and sorted

        await users.update_profile_field(session, user, "weight_kg", "80,5")
        assert user.profile.weight_kg == 80.5

        with pytest.raises(ValidationError):
            await users.update_profile_field(session, user, "age", "12")
        with pytest.raises(ValueError):
            await users.update_profile_field(session, user, "goal", "cut")


async def test_get_or_create_is_idempotent(session_factory):
    async with session_factory() as session:
        a = await users.get_or_create_user(session, 222)
        b = await users.get_or_create_user(session, 222)
        assert a.id == b.id
        assert await users.count_users(session) == 1


async def test_delete_removes_all_user_data_but_not_exercises(session_factory):
    async with session_factory() as session:
        user = await users.get_or_create_user(session, 333)
        await users.save_profile(session, user, VALID)
        session.add(Exercise(id="plank-main", name="Plank", muscle_group="core",
                             equipment="bodyweight", difficulty="beginner",
                             movement_type="isometric", home_friendly=True))
        await session.commit()

    async with session_factory() as session:
        assert await users.delete_user_data(session, 333) is True
        assert await users.delete_user_data(session, 333) is False

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 0
        # The profile row must be gone too (database-level ON DELETE CASCADE).
        assert await session.scalar(select(func.count()).select_from(Profile)) == 0
        assert await session.scalar(select(func.count()).select_from(Exercise)) == 1
