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
