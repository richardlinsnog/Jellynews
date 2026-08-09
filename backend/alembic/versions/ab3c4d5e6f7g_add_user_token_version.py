


"""Add token_version column to users table for refresh token rotation.

Revision ID: ab3c4d5e6f7g
Revises: 2a3b4c5d6e7f
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ab3c4d5e6f7g"
down_revision: str | None = "2a3b4c5d6e7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("token_version")
