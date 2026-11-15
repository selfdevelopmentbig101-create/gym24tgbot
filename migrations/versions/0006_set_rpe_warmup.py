"""set_logs.rpe and set_logs.warmup (Stage 5 live logger)

Superset groups and exercise notes live in workout_sessions.items (JSON), so
they need no new columns.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("set_logs") as batch:
        # How hard the set felt (1-10, optional).
        batch.add_column(sa.Column("rpe", sa.Float(), nullable=True))
        # Warm-up sets don't count for PRs, progression or volume. Old sets are working sets.
        batch.add_column(sa.Column("warmup", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("set_logs") as batch:
        batch.drop_column("warmup")
        batch.drop_column("rpe")
