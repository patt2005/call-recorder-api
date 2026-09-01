"""create_telnyx_error_logs

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-08-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'i0j1k2l3m4n5'
down_revision = 'h9i0j1k2l3m4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'telnyx_error_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('error_type', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('platform', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_telnyx_error_logs_error_type', 'telnyx_error_logs', ['error_type'])
    op.create_index('ix_telnyx_error_logs_created_at', 'telnyx_error_logs', ['created_at'])


def downgrade():
    op.drop_index('ix_telnyx_error_logs_created_at', table_name='telnyx_error_logs')
    op.drop_index('ix_telnyx_error_logs_error_type', table_name='telnyx_error_logs')
    op.drop_table('telnyx_error_logs')
