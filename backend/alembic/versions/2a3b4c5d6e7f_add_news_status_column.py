

"""Add status column to custom_news (Draft → Scheduled → Sent workflow)

Revision ID: 2a3b4c5d6e7f
Revises: e5a1b2c3d4f6
Create Date: 2026-08-09 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2a3b4c5d6e7f"
down_revision: Union[str, None] = "e5a1b2c3d4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite handles ENUM as VARCHAR with CHECK constraint
    with op.batch_alter_table("custom_news") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="draft",
            )
        )

    # Drop the deprecated published column
    with op.batch_alter_table("custom_news") as batch_op:
        batch_op.drop_column("published")


def downgrade() -> None:
    with op.batch_alter_table("custom_news") as batch_op:
        batch_op.add_column(
            sa.Column(
                "published",
                sa.Boolean(),
                server_default=sa.text("'true'"),
                nullable=False,
            )
        )

    with op.batch_alter_table("custom_news") as batch_op:
        batch_op.drop_column("status")

