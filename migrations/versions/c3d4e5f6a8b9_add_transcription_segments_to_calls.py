"""add transcription_segments to calls

Revision ID: c3d4e5f6a8b9
Revises: b2c3d4e5f6a8
Create Date: 2025-03-09

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a8b9'
down_revision = 'b2c3d4e5f6a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('calls', sa.Column('transcription_segments', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('calls', 'transcription_segments')
