"""
0002 – Core tables: change_requests, entries, instance tracking
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── change_requests ────────────────────────────────────────────────────
    op.create_table(
        "change_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("module", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("request_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("uploaded_file_name", sa.String(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_instances", JSONB, nullable=True),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_change_request_status", "change_requests", ["status"])
    op.create_index("idx_change_request_created", "change_requests", ["created_at"])

    # ── prr_entries ────────────────────────────────────────────────────────
    op.create_table(
        "prr_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_id", sa.String(), sa.ForeignKey("change_requests.id"), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("operator", sa.String(), nullable=True),
        sa.Column("mcc", sa.String(), nullable=True),
        sa.Column("mnc", sa.String(), nullable=True),
        sa.Column("realm", sa.String(), nullable=True),
        sa.Column("prt_rule", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False, server_default="ADD"),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_prr_entry_request", "prr_entries", ["request_id"])
    op.create_index("idx_prr_entry_realm", "prr_entries", ["realm"])

    # ── rbar_entries ───────────────────────────────────────────────────────
    op.create_table(
        "rbar_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_id", sa.String(), sa.ForeignKey("change_requests.id"), nullable=False),
        sa.Column("realm", sa.String(), nullable=True),
        sa.Column("start_addr", sa.BigInteger(), nullable=True),
        sa.Column("end_addr", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(), nullable=False, server_default="ADD"),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rbar_entry_request", "rbar_entries", ["request_id"])
    op.create_index("idx_rbar_entry_range", "rbar_entries", ["start_addr", "end_addr"])

    # ── entry_instance_statuses ────────────────────────────────────────────
    op.create_table(
        "entry_instance_statuses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),   # PRR | RBAR
        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("impl_status", sa.String(), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_entry_instance_status",
        "entry_instance_statuses",
        ["entry_id", "entry_type", "dra_type", "instance_label"],
    )
    op.create_index("idx_instance_status_lookup", "entry_instance_statuses",
                    ["dra_type", "instance_label"])
    op.create_index("idx_instance_status_impl", "entry_instance_statuses",
                    ["entry_type", "impl_status"])
    op.create_index("idx_instance_status_reconciled", "entry_instance_statuses",
                    ["last_reconciled_at"])

    # ── entry_instance_details ─────────────────────────────────────────────
    op.create_table(
        "entry_instance_details",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("instance_status_id", sa.String(),
                  sa.ForeignKey("entry_instance_statuses.id"), nullable=False),
        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),
        sa.Column("final_prt_rule", sa.String(), nullable=True),
        sa.Column("realm", sa.String(), nullable=True),
        sa.Column("start_addr", sa.BigInteger(), nullable=True),
        sa.Column("end_addr", sa.BigInteger(), nullable=True),
        sa.Column("destination", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_detail_status_id", "entry_instance_details", ["instance_status_id"])
    op.create_index("idx_detail_entry", "entry_instance_details", ["entry_id", "entry_type"])
    op.create_index("idx_detail_realm", "entry_instance_details", ["realm"])

    # ── audit_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_id", sa.String(), sa.ForeignKey("change_requests.id"), nullable=True),
        sa.Column("level", sa.String(), nullable=False, server_default="INFO"),
        sa.Column("entry_type", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("instance_label", sa.String(), nullable=True),
        sa.Column("dra_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_audit_request", "audit_logs", ["request_id"])
    op.create_index("idx_audit_created", "audit_logs", ["created_at"])
    op.create_index("idx_audit_level", "audit_logs", ["level"])

    op.create_table(
        "entry_instance_relationships",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("instance_status_id", sa.String(), sa.ForeignKey("entry_instance_statuses.id"), nullable=False),
        sa.Column("related_request_id", sa.String(), sa.ForeignKey("change_requests.id"), nullable=False),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("relationship_match_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_relationship_type","entry_instance_relationships",["relationship_type"])
    op.create_unique_constraint(
        "uq_entry_instance_relationship_fields",   # Constraint name
        "entry_instance_relationships",            # Table name
        ["instance_status_id", "related_request_id", "relationship_type"] # Columns
    )

def downgrade() -> None:
    op.drop_constraint("uq_entry_instance_relationship_fields", "entry_instance_relationships", type_="unique")
    for t in [
        "audit_logs", "entry_instance_details", "entry_instance_relationships", "entry_instance_statuses",
        "rbar_entries", "prr_entries", "change_requests",
    ]:
        op.drop_table(t)
