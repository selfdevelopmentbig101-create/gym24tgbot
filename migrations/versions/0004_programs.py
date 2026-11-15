"""programs: several plans per user (one current), names, weeks, training goal

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workout_plans") as batch:
        # One user can now have several programs.
        batch.drop_index("ix_workout_plans_user_id")
        batch.create_index("ix_workout_plans_user_id", ["user_id"], unique=False)
        batch.add_column(sa.Column("name", sa.String(60), nullable=True))
        batch.add_column(sa.Column("kind", sa.String(10), nullable=False, server_default="template"))
        batch.add_column(sa.Column("template_days", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("goal", sa.String(12), nullable=False, server_default="hypertrophy"))
        batch.add_column(sa.Column("weeks", sa.Integer(), nullable=False, server_default="8"))
        batch.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("edited", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("started_on", sa.Date(), nullable=True))
    # Existing plans: the generated one-per-user plan becomes the current program.
    op.execute("UPDATE workout_plans SET template_days = (SELECT COUNT(*) FROM plan_days "
               "WHERE plan_days.plan_id = workout_plans.id), started_on = DATE(created_at)")
    with op.batch_alter_table("plan_days") as batch:
        batch.alter_column("name_key", type_=sa.String(40), existing_type=sa.String(20), existing_nullable=False)
    with op.batch_alter_table("workout_sessions") as batch:
        batch.alter_column("name_key", type_=sa.String(40), existing_type=sa.String(20), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("workout_plans") as batch:
        for name in ("started_on", "edited", "is_current", "weeks", "goal", "template_days", "kind", "name"):
            batch.drop_column(name)
        batch.drop_index("ix_workout_plans_user_id")
        batch.create_index("ix_workout_plans_user_id", ["user_id"], unique=True)
