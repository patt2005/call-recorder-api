"""create call_transcripts table

Revision ID: d4e5f6a8b9c0
Revises: c3d4e5f6a8b9
Create Date: 2025-03-09

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a8b9c0'
down_revision = 'c3d4e5f6a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'call_transcripts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('call_id', sa.String(length=100), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('segments', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('language', sa.String(length=20), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['call_id'], ['calls.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('call_id', name='uq_call_transcripts_call_id'),
    )


def downgrade():
    op.drop_table('call_transcripts')
