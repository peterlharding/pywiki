"""add_email_verification

Revision ID: a1b2c3d4e5f6
Revises: 58579c489d29
Create Date: 2026-03-01 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '58579c489d29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_verified',      sa.Boolean(),              nullable=False, server_default='0'))
    op.add_column('users', sa.Column('verification_token',  sa.String(length=128),     nullable=True))
    op.add_column('users', sa.Column('reset_token',         sa.String(length=128),     nullable=True))
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_users_verification_token', 'users', ['verification_token'], unique=False)
    op.create_index('ix_users_reset_token',        'users', ['reset_token'],        unique=False)


def downgrade() -> None:
    op.drop_index('ix_users_reset_token',        table_name='users')
    op.drop_index('ix_users_verification_token', table_name='users')
    op.drop_column('users', 'reset_token_expires')
    op.drop_column('users', 'reset_token')
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'email_verified')
