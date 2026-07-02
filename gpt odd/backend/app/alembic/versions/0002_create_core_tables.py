from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0002"
down_revision = "0001"


def upgrade():

    # =====================================================
    # CHANGE REQUESTS
    # =====================================================

    op.create_table(
        "change_requests",

        sa.Column("id", sa.String(), primary_key=True),

        sa.Column("module", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),

        sa.Column("request_version", sa.Integer(), nullable=False, server_default="1"),

        sa.Column("uploaded_file_name", sa.String()),

        sa.Column("total_rows", sa.Integer(), server_default="0"),
        sa.Column("processed_rows", sa.Integer(), server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), server_default="0"),
        sa.Column("failed_rows", sa.Integer(), server_default="0"),

        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),

        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # =====================================================
    # PRR ENTRIES
    # =====================================================

    op.create_table(
        "prr_entries",

        sa.Column("id", sa.String(), primary_key=True),

        sa.Column(
            "request_id",
            sa.String(),
            sa.ForeignKey("change_requests.id"),
            nullable=False,
        ),

        sa.Column("country", sa.String()),
        sa.Column("operator", sa.String()),
        sa.Column("mcc", sa.String()),
        sa.Column("mnc", sa.String()),

        sa.Column("realm", sa.String(), nullable=False),
        sa.Column("prt_rule", sa.String(), nullable=False),

        sa.Column("action", sa.String(), nullable=False),

        sa.Column("raw_payload", JSONB),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # =====================================================
    # RBAR ENTRIES
    # =====================================================

    op.create_table(
        "rbar_entries",

        sa.Column("id", sa.String(), primary_key=True),

        sa.Column(
            "request_id",
            sa.String(),
            sa.ForeignKey("change_requests.id"),
            nullable=False,
        ),

        sa.Column("realm", sa.String()),

        sa.Column("start_addr", sa.BigInteger(), nullable=False),
        sa.Column("end_addr", sa.BigInteger(), nullable=False),

        sa.Column("action", sa.String(), nullable=False),

        sa.Column("raw_payload", JSONB),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # =====================================================
    # ENTRY INSTANCE STATUS
    # =====================================================

    op.create_table(
        "entry_instance_statuses",

        sa.Column("id", sa.String(), primary_key=True),

        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),

        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),

        sa.Column("decision", sa.String()),
        sa.Column("reason", sa.String()),

        sa.Column("dependency_note", sa.String()),

        sa.Column(
            "dependency_request_id",
            sa.String(),
            sa.ForeignKey("change_requests.id"),
        ),

        sa.Column("impl_status", sa.String()),

        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # =====================================================
    # ENTRY INSTANCE DETAIL
    # =====================================================

    op.create_table(
        "entry_instance_details",

        sa.Column("id", sa.String(), primary_key=True),

        sa.Column(
            "instance_status_id",
            sa.String(),
            sa.ForeignKey("entry_instance_statuses.id"),
            nullable=False,
        ),

        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),

        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),

        sa.Column("final_prt_rule", sa.String()),
        sa.Column("realm", sa.String()),

        sa.Column("start_addr", sa.BigInteger()),
        sa.Column("end_addr", sa.BigInteger()),

        sa.Column("destination", sa.String()),

        sa.Column("raw_payload", JSONB),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )