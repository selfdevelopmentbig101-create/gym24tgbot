"""exercises.visual_type ("images" now; room for generated animations later)

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
    # Every existing exercise uses the RepDB images, so "images" is the right default.
    with op.batch_alter_table("exercises") as batch:
        batch.add_column(sa.Column("visual_type", sa.String(length=16), nullable=False,
                                   server_default="images"))


def downgrade() -> None:
    with op.batch_alter_table("exercises") as batch:
        batch.drop_column("visual_type")
