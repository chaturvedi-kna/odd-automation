"""
0006 – Instance label format change:
    old: {SITE}-{INDEX:02d}            (sequential across categories, e.g. DEL-01 … DEL-14)
    new: {SITE}-{CATEGORY}-{INDEX:02d} (index restarts per category, e.g. DEL-CORE-01)

Relabels dra_instances AND every table that stores instance_label
denormalized (dump_snapshots, entry_instance_statuses,
entry_instance_details, unknown_entries).

Fresh installs seed the new format directly in 0003, so the old→new
mapping simply matches nothing and this migration is a no-op.
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Must mirror the seed tables in 0003 exactly — the old sequential index is
# reconstructed from the same site/category ordering used at seed time.
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
CATEGORY_ORDER = ["Core", "Charging", "Policy", "Layer", "DR", "IoT"]

LABEL_TABLES = [
    "dra_instances",
    "dump_snapshots",
    "entry_instance_statuses",
    "entry_instance_details",
    "unknown_entries",
]


def _label_mapping() -> list[tuple[str, str, str]]:
    """Yield (dra_type, old_label, new_label) for every seeded instance."""
    mapping = []
    for dra_type, sites in (("BM-DRA", BM_DRA_SITES), ("V-DRA", V_DRA_SITES)):
        for site, cats in sites.items():
            seq = 1  # old sequential index across categories
            for cat in CATEGORY_ORDER:
                for i in range(1, cats.get(cat, 0) + 1):
                    old = f"{site}-{seq:02d}"
                    new = f"{site}-{cat.upper()}-{i:02d}"
                    mapping.append((dra_type, old, new))
                    seq += 1
    return mapping


def _apply(mapping: list[tuple[str, str, str]]) -> None:
    conn = op.get_bind()
    for table in LABEL_TABLES:
        for dra_type, old, new in mapping:
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET instance_label = :new "
                    f"WHERE dra_type = :dt AND instance_label = :old"
                ),
                {"new": new, "dt": dra_type, "old": old},
            )


def upgrade() -> None:
    _apply(_label_mapping())


def downgrade() -> None:
    _apply([(dt, new, old) for dt, old, new in _label_mapping()])
