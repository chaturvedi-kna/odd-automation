"""
0003 – Dump tables, DRA instances, notifications, app settings, unknown entries + seed
"""
import uuid
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# ── DRA infrastructure seed ────────────────────────────────────────────────────

BM_DRA_SITES = {
    "DEL": {"Core": 3, "Charging": 4, "Policy": 4, "Layer": 2, "DR": 0, "IoT": 1},
    "KOL": {"Core": 3, "Charging": 4, "Policy": 4, "Layer": 2, "DR": 0, "IoT": 1},
    "MUM": {"Core": 2, "Charging": 2, "Policy": 2, "Layer": 2, "DR": 0, "IoT": 1},
    "BLR": {"Core": 2, "Charging": 2, "Policy": 2, "Layer": 2, "DR": 0, "IoT": 1},
    "LKN": {"Core": 3, "Charging": 4, "Policy": 4, "Layer": 0, "DR": 0, "IoT": 1},
    "AHM": {"Core": 3, "Charging": 4, "Policy": 4, "Layer": 0, "DR": 0, "IoT": 1},
    "HYD": {"Core": 3, "Charging": 4, "Policy": 4, "Layer": 0, "DR": 0, "IoT": 1},
    "NGP": {"Core": 3, "Charging": 4, "Policy": 4, "Layer": 0, "DR": 2, "IoT": 1},
}

V_DRA_SITES = {
    "DEL": {"Core": 2, "Charging": 3, "Policy": 3, "Layer": 1, "DR": 0, "IoT": 1},
    "KOL": {"Core": 2, "Charging": 3, "Policy": 3, "Layer": 1, "DR": 0, "IoT": 1},
    "BH":  {"Core": 1, "Charging": 0, "Policy": 2, "Layer": 0, "DR": 0, "IoT": 0},
    "WB":  {"Core": 1, "Charging": 0, "Policy": 2, "Layer": 0, "DR": 0, "IoT": 0},
    "HYD": {"Core": 2, "Charging": 3, "Policy": 3, "Layer": 0, "DR": 0, "IoT": 1},
    "NGP": {"Core": 2, "Charging": 3, "Policy": 3, "Layer": 0, "DR": 2, "IoT": 1},
    "TN":  {"Core": 1, "Charging": 0, "Policy": 3, "Layer": 0, "DR": 0, "IoT": 0},
    "MP":  {"Core": 1, "Charging": 0, "Policy": 3, "Layer": 0, "DR": 0, "IoT": 0},
    "UPE": {"Core": 1, "Charging": 3, "Policy": 2, "Layer": 0, "DR": 0, "IoT": 1},
    "GJ":  {"Core": 1, "Charging": 3, "Policy": 2, "Layer": 0, "DR": 0, "IoT": 1},
    "UPW": {"Core": 1, "Charging": 0, "Policy": 2, "Layer": 0, "DR": 0, "IoT": 0},
    "RJ":  {"Core": 1, "Charging": 0, "Policy": 2, "Layer": 0, "DR": 0, "IoT": 0},
    "MUM": {"Core": 1, "Charging": 1, "Policy": 2, "Layer": 1, "DR": 0, "IoT": 1},
    "BLR": {"Core": 1, "Charging": 1, "Policy": 2, "Layer": 1, "DR": 0, "IoT": 1},
}

CAT_ABBREV = {
    "Core": "COR", "Charging": "CHR", "Policy": "POL",
    "Layer": "LAY", "DR": "DR", "IoT": "IOT",
}
CATEGORY_ORDER = ["Core", "Charging", "Policy", "Layer", "DR", "IoT"]


def _build_instances(dra_type: str, sites: dict) -> list[dict]:
    """
    Build DRA instance rows with sequential instance_label across categories.
    Format: {SITE}-{INDEX:02d}  (e.g. DEL-01 … DEL-19)
    """
    rows = []
    for site, cats in sites.items():
        idx = 1
        for cat in CATEGORY_ORDER:
            count = cats.get(cat, 0)
            if count == 0:
                continue
            for _ in range(count):
                rows.append({
                    "id": str(uuid.uuid4()),
                    "dra_type": dra_type,
                    "site": site,
                    "category": cat,
                    "category_abbrev": CAT_ABBREV[cat],
                    "instance_label": f"{site}-{idx:02d}",
                    "is_active": True,
                })
                idx += 1
    return rows


def upgrade() -> None:
    # ── dra_instances ──────────────────────────────────────────────────────
    op.create_table(
        "dra_instances",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("site", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("category_abbrev", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_dra_instance", "dra_instances", ["dra_type", "instance_label"])
    op.create_index("idx_dra_instance_lookup", "dra_instances", ["dra_type", "instance_label"])
    op.create_index("idx_dra_site_category", "dra_instances", ["site", "category"])
    op.create_index("idx_dra_active", "dra_instances", ["is_active"])

    # Seed
    all_instances = (
        _build_instances("BM-DRA", BM_DRA_SITES)
        + _build_instances("V-DRA", V_DRA_SITES)
    )
    if all_instances:
        op.bulk_insert(
            sa.table(
                "dra_instances",
                sa.column("id"), sa.column("dra_type"), sa.column("site"),
                sa.column("category"), sa.column("category_abbrev"),
                sa.column("instance_label"), sa.column("is_active"),
            ),
            all_instances,
        )

    # ── dump_snapshots ─────────────────────────────────────────────────────
    op.create_table(
        "dump_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),
        sa.Column("object_type", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_dump_snapshot_lookup", "dump_snapshots",
                    ["dra_type", "instance_label", "object_type"])
    op.create_index("idx_dump_snapshot_created", "dump_snapshots", ["created_at"])

    # ── prr_dump_rows ──────────────────────────────────────────────────────
    op.create_table(
        "prr_dump_rows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("snapshot_id", sa.String(), sa.ForeignKey("dump_snapshots.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("realm", sa.String(), nullable=True),
        sa.Column("route_list_name", sa.String(), nullable=True),
        sa.Column("peer_route_table", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_prr_row_snapshot", "prr_dump_rows", ["snapshot_id"])
    op.create_index("idx_prr_row_realm", "prr_dump_rows", ["realm"])

    # ── rbar_dump_rows ─────────────────────────────────────────────────────
    op.create_table(
        "rbar_dump_rows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("snapshot_id", sa.String(), sa.ForeignKey("dump_snapshots.id"), nullable=False),
        sa.Column("table_name", sa.String(), nullable=True),
        sa.Column("start_addr", sa.BigInteger(), nullable=True),
        sa.Column("end_addr", sa.BigInteger(), nullable=True),
        sa.Column("destination", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rbar_row_snapshot", "rbar_dump_rows", ["snapshot_id"])
    op.create_index("idx_rbar_row_range", "rbar_dump_rows", ["start_addr", "end_addr"])

    # ── notifications ──────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("related_request_id", sa.String(),
                  sa.ForeignKey("change_requests.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_notification_unread", "notifications", ["is_read", "created_at"])

    # ── app_settings ───────────────────────────────────────────────────────
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("download_base_name", sa.String(), nullable=True, server_default="ODD"),
        sa.Column("download_version", sa.String(), nullable=True, server_default="1.0"),
        sa.Column("recon_cron_time", sa.String(), nullable=True, server_default="02:00"),
        sa.Column("dump_ingest_times", sa.String(), nullable=True, server_default="06:00,18:00"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("INSERT INTO app_settings (id) VALUES (1) ON CONFLICT DO NOTHING")

    # ── unknown_entries ────────────────────────────────────────────────────
    op.create_table(
        "unknown_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dra_type", sa.String(), nullable=False),
        sa.Column("instance_label", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("identifier", sa.String(), nullable=False),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_unknown_entry", "unknown_entries",
        ["dra_type", "instance_label", "entry_type", "identifier"],
    )
    op.create_index("idx_unknown_entry_instance", "unknown_entries", ["dra_type", "instance_label"])
    op.create_index("idx_unknown_entry_ack", "unknown_entries", ["is_acknowledged"])


def downgrade() -> None:
    for t in [
        "unknown_entries", "app_settings", "notifications",
        "rbar_dump_rows", "prr_dump_rows", "dump_snapshots", "dra_instances",
    ]:
        op.drop_table(t)
