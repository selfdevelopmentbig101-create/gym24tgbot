"""exercises.secondary_muscles (library search and detail)

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Filled by the exercise import, which runs on every bot start.
    with op.batch_alter_table("exercises") as batch:
        batch.add_column(sa.Column("secondary_muscles", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("exercises") as batch:
        batch.drop_column("secondary_muscles")
