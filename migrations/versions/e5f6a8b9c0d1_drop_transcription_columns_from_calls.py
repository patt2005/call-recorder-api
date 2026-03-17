"""drop transcription columns from calls

Revision ID: e5f6a8b9c0d1
Revises: d4e5f6a8b9c0
Create Date: 2025-03-16

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a8b9c0d1'
down_revision = 'd4e5f6a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('calls', 'transcription_text')
    op.drop_column('calls', 'transcription_status')
    op.drop_column('calls', 'transcription_segments')


def downgrade():
    op.add_column('calls', sa.Column('transcription_text', sa.Text(), nullable=True))
    op.add_column('calls', sa.Column('transcription_status', sa.String(length=20), nullable=True))
    op.add_column('calls', sa.Column('transcription_segments', sa.Text(), nullable=True))

