from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"


def upgrade():

    # =====================================================
    # UNIQUE CONSTRAINTS
    # =====================================================

    op.create_unique_constraint(
        "uq_entry_instance_status",
        "entry_instance_statuses",
        [
            "entry_id",
            "entry_type",
            "dra_type",
            "instance_label",
        ],
    )

    # =====================================================
    # INDEXES
    # =====================================================

    op.create_index(
        "idx_prr_realm",
        "prr_entries",
        ["realm"],
    )

    op.create_index(
        "idx_prr_rule",
        "prr_entries",
        ["prt_rule"],
    )

    op.create_index(
        "idx_rbar_range",
        "rbar_entries",
        ["start_addr", "end_addr"],
    )

    op.create_index(
        "idx_instance_status_lookup",
        "entry_instance_statuses",
        ["dra_type", "instance_label"],
    )

    op.create_index(
        "idx_instance_status_reconciled",
        "entry_instance_statuses",
        ["last_reconciled_at"],
    )

    op.create_index(
        "idx_change_request_status",
        "change_requests",
        ["status"],
    )