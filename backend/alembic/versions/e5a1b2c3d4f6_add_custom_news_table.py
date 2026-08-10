"""add custom_news table

Revision ID: e5a1b2c3d4f6
Revises: d70c1b7e6ff5
Create Date: 2026-08-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a1b2c3d4f6'
down_revision: Union[str, None] = 'd70c1b7e6ff5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'custom_news',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('published', sa.Boolean(), server_default='true', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_custom_news_created_at', 'custom_news', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_custom_news_created_at')
    op.drop_table('custom_news')
