

"""Add destination_type column and rename email to destination in subscribers table.

Revision ID: 8a1b2c3d4e5f
Revises: fa7deb630522
Create Date: 2026-08-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a1b2c3d4e5f"
down_revision: Union[str, None] = "fa7deb630522"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("subscribers") as batch_op:
        batch_op.alter_column("email", new_column_name="destination")
        batch_op.add_column(
            sa.Column(
                "destination_type",
                sa.String(20),
                nullable=False,
                server_default="email",
            ),
        )
        batch_op.create_index(
            op.f("ix_subscribers_destination_type"),
            ["destination_type"],
        )


def downgrade() -> None:
    with op.batch_alter_table("subscribers") as batch_op:
        batch_op.drop_index(op.f("ix_subscribers_destination_type"))
        batch_op.drop_column("destination_type")
        batch_op.alter_column("destination", new_column_name="email")

