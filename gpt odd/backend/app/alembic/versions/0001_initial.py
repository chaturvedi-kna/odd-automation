from alembic import op
import sqlalchemy as sa
import uuid
import bcrypt


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ENUMS
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE request_status_enum AS ENUM (
            'QUEUED','PROCESSING','DONE','DONE_PARTIAL','FAILED'
        );
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE entry_status_enum AS ENUM (
            'SENT','RENAMED','SKIPPED','REJECTED'
        );
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE user_role_enum AS ENUM (
            'admin','operator','viewer'
        );
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    """)

    # USERS
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ADMIN SEED
    hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()

    op.execute(
        sa.text("""
        INSERT INTO users (id, username, password_hash, role, is_active)
        VALUES (:id, 'admin', :pwd, 'admin', true)
        ON CONFLICT (username) DO NOTHING
        """),
        {"id": str(uuid.uuid4()), "pwd": hashed},
    )


def downgrade():
    op.drop_table("users")