"""
Database tables.

Privacy: we store only what the features need. No names, usernames or phone
numbers. Every user-owned table links to users.id with ON DELETE CASCADE, so
deleting the user row (/deleteme) removes all of their data. Tables added in
later phases (workouts, sets, body weight, meals...) must follow the same rule.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from database.enums import Diet, Equipment, Experience, Goal, Sex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def str_enum(enum_cls):
    """Store the enum's value ("lean_bulk") as VARCHAR, not a native DB enum type."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda e: [member.value for member in e],
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Telegram IDs can exceed 32 bits, hence BigInteger.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    language_code: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Set when the user accepts the health disclaimer; onboarding needs it.
    disclaimer_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class Profile(Base):
    """Answers from onboarding. Calorie/protein targets are computed from this on demand."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    goal: Mapped[Goal] = mapped_column(str_enum(Goal))
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[Sex] = mapped_column(str_enum(Sex))
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    experience: Mapped[Experience] = mapped_column(str_enum(Experience))
    training_days: Mapped[int] = mapped_column(Integer)
    equipment: Mapped[Equipment] = mapped_column(str_enum(Equipment))
    # List of Injury values, e.g. ["knee", "shoulder"]. Empty list = none.
    injuries: Mapped[list[str]] = mapped_column(JSON, default=list)
    diet: Mapped[Diet] = mapped_column(str_enum(Diet))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Exercise(Base):
    """
    The curated exercise list (filled from data/core_exercises.json by the
    import script in Phase 2). Plans are generated only from this table.
    Not user data, so /deleteme never touches it.
    """

    __tablename__ = "exercises"

    # Slug such as "barbell-bench-press". Also the base name of the image files.
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    muscle_group: Mapped[str] = mapped_column(String(40), index=True)
    equipment: Mapped[str] = mapped_column(String(40), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    movement_type: Mapped[str] = mapped_column(String(40))
    home_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    # IDs of other exercises in this table; the import script validates them.
    substitute_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Short coaching cues, filled in by hand later.
    form_tips: Mapped[str | None] = mapped_column(Text, nullable=True)
    # False if the exercise was removed from the JSON. It's kept (old plans and
    # logs may point to it) but no longer offered.
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Position in core_exercises.json; keeps your curated order (earlier = preferred).
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class WorkoutPlan(Base):
    """A user's generated plan. One active plan per user; regenerating replaces it."""

    __tablename__ = "workout_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    split: Mapped[str] = mapped_column(String(30))  # e.g. "full_body", "upper_lower"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    days: Mapped[list["PlanDay"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlanDay.day_index",
        lazy="selectin",
    )


class PlanDay(Base):
    __tablename__ = "plan_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="CASCADE"), index=True
    )
    day_index: Mapped[int] = mapped_column(Integer)  # 0-based order in the week
    name_key: Mapped[str] = mapped_column(String(20))  # text key: "upper", "push"...
    suffix: Mapped[str] = mapped_column(String(4), default="")  # "A", "B" or ""

    plan: Mapped[WorkoutPlan] = relationship(back_populates="days")
    exercises: Mapped[list["PlanExercise"]] = relationship(
        back_populates="day",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlanExercise.position",
        lazy="selectin",
    )


class PlanExercise(Base):
    __tablename__ = "plan_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("plan_days.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    sets: Mapped[int] = mapped_column(Integer)
    rep_min: Mapped[int] = mapped_column(Integer)
    rep_max: Mapped[int] = mapped_column(Integer)
    # True when reps mean seconds (e.g. plank 30-45 s).
    timed: Mapped[bool] = mapped_column(Boolean, default=False)
    rest_seconds: Mapped[int] = mapped_column(Integer)

    day: Mapped[PlanDay] = relationship(back_populates="exercises", lazy="selectin")
    exercise: Mapped[Exercise] = relationship(lazy="selectin")


class MediaCache(Base):
    """
    Telegram file_ids of exercise media we already uploaded, so each image or
    animation is uploaded only once. Not user data.
    """

    __tablename__ = "media_cache"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(255))


class WorkoutSession(Base):
    """
    One workout. The exercise list is copied from the plan when the workout
    starts, so regenerating the plan mid-workout doesn't break it.
    The logger's draft (current exercise, weight and reps on the Log button)
    is stored here too, so it survives bot restarts and other menus.
    """

    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name_key: Mapped[str] = mapped_column(String(20), default="")
    suffix: Mapped[str] = mapped_column(String(4), default="")
    # [{"exercise_id", "sets", "rep_min", "rep_max", "timed", "rest_seconds"}, ...]
    items: Mapped[list[dict]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    current_index: Mapped[int] = mapped_column(Integer, default=0)
    draft_weight: Mapped[float] = mapped_column(Float, default=0)
    draft_reps: Mapped[int] = mapped_column(Integer, default=0)
    card_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    sets: Mapped[list["SetLog"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SetLog.id",
        lazy="selectin",
    )


class SetLog(Base):
    """One logged set. For timed exercises (plank) `reps` holds seconds."""

    __tablename__ = "set_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    # Duplicated from the session so history queries stay simple and fast.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True)
    set_number: Mapped[int] = mapped_column(Integer)  # 1-based, per exercise per workout
    weight_kg: Mapped[float] = mapped_column(Float, default=0)  # 0 = bodyweight only
    reps: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[WorkoutSession] = relationship(back_populates="sets")
