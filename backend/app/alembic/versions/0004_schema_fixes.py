"""
0004 – Schema fixes:
* rbar_dump_rows: add pfx_length / old_table_name / old_start_addr / old_pfx_length
  (columns the ingest task and exporter persist from the DSR dump)
* unknown_entries: add first_seen_at / last_seen_at lifecycle timestamps
* entry_instance_statuses: drop uq_entry_instance_status — a SUPERSEDE decision
  legitimately creates a second (DELETE) status row for the same
  entry/instance; replaced with a plain index.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── rbar_dump_rows extra dump columns ─────────────────────────────────
    op.add_column("rbar_dump_rows", sa.Column("pfx_length", sa.String(), nullable=True))
    op.add_column("rbar_dump_rows", sa.Column("old_table_name", sa.String(), nullable=True))
    op.add_column("rbar_dump_rows", sa.Column("old_start_addr", sa.BigInteger(), nullable=True))
    op.add_column("rbar_dump_rows", sa.Column("old_pfx_length", sa.String(), nullable=True))

    # ── unknown_entries lifecycle timestamps ──────────────────────────────
    op.add_column("unknown_entries", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("unknown_entries", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))

    # ── entry_instance_statuses: unique → plain index ─────────────────────
    op.drop_constraint("uq_entry_instance_status", "entry_instance_statuses", type_="unique")
    op.create_index(
        "idx_instance_status_entry",
        "entry_instance_statuses",
        ["entry_id", "entry_type", "dra_type", "instance_label"],
    )


def downgrade() -> None:
    op.drop_index("idx_instance_status_entry", table_name="entry_instance_statuses")
    op.create_unique_constraint(
        "uq_entry_instance_status",
        "entry_instance_statuses",
        ["entry_id", "entry_type", "dra_type", "instance_label"],
    )
    op.drop_column("unknown_entries", "last_seen_at")
    op.drop_column("unknown_entries", "first_seen_at")
    op.drop_column("rbar_dump_rows", "old_pfx_length")
    op.drop_column("rbar_dump_rows", "old_start_addr")
    op.drop_column("rbar_dump_rows", "old_table_name")
    op.drop_column("rbar_dump_rows", "pfx_length")
