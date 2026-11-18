"""workout_plans.active_day_index: the split (plan day) the user chose in Train

NULL = no choice; the app uses the next day in rotation.

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workout_plans") as batch:
        batch.add_column(sa.Column("active_day_index", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("workout_plans") as batch:
        batch.drop_column("active_day_index")
