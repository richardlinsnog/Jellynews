"""add tags column to subscribers

Revision ID: a1b2c3d4e5f6
Revises: d3b05b29bda6
Create Date: 2026-08-11 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d3b05b29bda6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("subscribers") as batch_op:
        batch_op.add_column(sa.Column("tags", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subscribers") as batch_op:
        batch_op.drop_column("tags")
