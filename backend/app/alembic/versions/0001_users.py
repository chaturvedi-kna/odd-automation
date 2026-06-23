"""
0001 – Initial users table and admin seed
"""
import uuid
import bcrypt
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), unique=True, nullable=False),
        sa.Column("email", sa.String(), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_email", "users", ["email"])

    # Seed admin user
    hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    op.execute(
        sa.text(
            "INSERT INTO users (id, username, email, hashed_password, role, is_active) "
            "VALUES (:id, 'admin', 'admin@odd.local', :pwd, 'admin', true) "
            "ON CONFLICT (username) DO NOTHING"
        ).bindparams(id=str(uuid.uuid4()), pwd=hashed)
    )


def downgrade() -> None:
    op.drop_table("users")
