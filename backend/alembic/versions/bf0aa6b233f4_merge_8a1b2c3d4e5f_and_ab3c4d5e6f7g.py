"""merge 8a1b2c3d4e5f and ab3c4d5e6f7g

Revision ID: bf0aa6b233f4
Revises: 8a1b2c3d4e5f, ab3c4d5e6f7g
Create Date: 2026-08-10 18:03:28.351749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf0aa6b233f4'
down_revision: Union[str, None] = ('8a1b2c3d4e5f', 'ab3c4d5e6f7g')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
