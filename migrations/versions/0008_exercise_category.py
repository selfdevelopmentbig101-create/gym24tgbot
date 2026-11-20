"""exercises.category: strength, stretching, cardio, olympic or plyometrics

Plans only use strength movements, while the library lists everything.

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every exercise before this migration was a strength movement.
    with op.batch_alter_table("exercises") as batch:
        batch.add_column(sa.Column("category", sa.String(length=20), nullable=False,
                                   server_default="strength"))


def downgrade() -> None:
    with op.batch_alter_table("exercises") as batch:
        batch.drop_column("category")
