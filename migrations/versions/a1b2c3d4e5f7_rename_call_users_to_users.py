"""rename call_users to users

Revision ID: a1b2c3d4e5f7
Revises: 6673ddd78a06
Create Date: 2025-03-05

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '6673ddd78a06'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('call_users', 'users')


def downgrade():
    op.rename_table('users', 'call_users')
