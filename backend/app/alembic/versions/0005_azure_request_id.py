"""
0005 – Add azure_request_id to change_requests (external ticket reference
captured when a new request is created).
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("change_requests", sa.Column("azure_request_id", sa.String(), nullable=True))
    op.create_index("idx_change_request_azure", "change_requests", ["azure_request_id"])


def downgrade() -> None:
    op.drop_index("idx_change_request_azure", table_name="change_requests")
    op.drop_column("change_requests", "azure_request_id")
