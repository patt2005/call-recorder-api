"""remove phone_number unique constraint from users

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2025-03-09

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a8'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    # Drop unique constraint on phone_number. Name may be call_users_phone_number_key
    # (if table was renamed from call_users) or users_phone_number_key (if table is users).
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_users_phone_number_key' AND conrelid = 'users'::regclass) THEN
                ALTER TABLE users DROP CONSTRAINT call_users_phone_number_key;
            ELSIF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_phone_number_key' AND conrelid = 'users'::regclass) THEN
                ALTER TABLE users DROP CONSTRAINT users_phone_number_key;
            END IF;
        END $$;
    """)


def downgrade():
    op.create_unique_constraint('users_phone_number_key', 'users', ['phone_number'])
