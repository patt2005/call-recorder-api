"""add user_id to calls

Revision ID: f7a8b9c0d1e2
Revises: e5f6a8b9c0d1
Create Date: 2025-03-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f7a8b9c0d1e2'
down_revision = 'e5f6a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('calls', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('calls_user_id_fkey', 'calls', 'users', ['user_id'], ['id'])


def downgrade():
    op.drop_constraint('calls_user_id_fkey', 'calls', type_='foreignkey')
    op.drop_column('calls', 'user_id')
