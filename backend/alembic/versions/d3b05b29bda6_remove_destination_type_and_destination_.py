"""remove_destination_type_and_destination_from_subscribers

Revision ID: d3b05b29bda6
Revises: bf0aa6b233f4
Create Date: 2026-08-11 15:40:42.467144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3b05b29bda6'
down_revision: Union[str, None] = 'bf0aa6b233f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: subscribers table already created with final schema in fa7deb630522.
    pass


def downgrade() -> None:
    with op.batch_alter_table("subscribers") as batch_op:
        batch_op.add_column(sa.Column("destination_type", sa.VARCHAR(length=20), server_default=sa.text("'email'"), nullable=False))
        batch_op.add_column(sa.Column("destination", sa.VARCHAR(length=320), nullable=False))
        batch_op.create_index("ix_subscribers_destination_type", ["destination_type"], unique=False)
        batch_op.create_index("ix_subscribers_destination", ["destination"], unique=False)
