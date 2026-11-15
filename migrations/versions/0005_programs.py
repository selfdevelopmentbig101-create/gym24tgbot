"""programs table (Stage 4) and plan_days.title (day names from the split editor)

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("template", sa.String(length=20), nullable=True),
        sa.Column("goal", sa.String(length=12), nullable=False),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("workouts_per_week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("days_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Deleting the user (/deleteme) deletes their programs.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("programs") as batch:
        batch.create_index(batch.f("ix_programs_user_id"), ["user_id"], unique=False)
    with op.batch_alter_table("plan_days") as batch:
        batch.add_column(sa.Column("title", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plan_days") as batch:
        batch.drop_column("title")
    with op.batch_alter_table("programs") as batch:
        batch.drop_index(batch.f("ix_programs_user_id"))
    op.drop_table("programs")
