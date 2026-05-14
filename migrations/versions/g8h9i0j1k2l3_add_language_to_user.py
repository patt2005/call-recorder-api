"""add_language_to_user

Revision ID: g8h9i0j1k2l3
Revises: 3593b0e93e82
Create Date: 2026-05-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g8h9i0j1k2l3'
down_revision = '3593b0e93e82'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('language', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('language')
