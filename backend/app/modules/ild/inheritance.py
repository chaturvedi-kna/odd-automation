import logging
from sqlalchemy import select, and_
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.dump_snapshot import DumpSnapshot

logger = logging.getLogger(__name__)


async def _get_latest_snapshot(db, dra_type: str, instance_label: str, obj_type: str):
    return (
        await db.execute(
            select(DumpSnapshot)
            .where(
                and_(
                    DumpSnapshot.dra_type == dra_type,
                    DumpSnapshot.instance_label == instance_label,
                    DumpSnapshot.object_type == obj_type,
                )
            )
            .order_by(DumpSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalars().first()


async def inherit_prr_template(
    db,
    dra_type: str,
    instance_label: str,
    override: dict | None = None,   # FIX: removed unused `realm` param; processor was omitting it
) -> dict:
    """
    Return a payload dict seeded from the latest PRR dump row template,
    with ``override`` keys merged on top.
    """
    snapshot = await _get_latest_snapshot(db, dra_type, instance_label, "PRR")

    if not snapshot:
        logger.debug("No PRR snapshot for %s %s – using override only", dra_type, instance_label)
        return dict(override or {})

    rows = (
        await db.execute(
            select(PrrDumpRow).where(PrrDumpRow.snapshot_id == snapshot.id).limit(1)
        )
    ).scalars().all()

    if rows:
        base = dict(rows[0].raw_payload or {})
        base.update(override or {})
        return base

    return dict(override or {})


async def inherit_rbar_template(
    db,
    dra_type: str,
    instance_label: str,
    override: dict | None = None,   # FIX: removed `start`/`end` params processor didn't pass
) -> dict:
    """
    Return a payload dict seeded from the latest RBAR dump row template,
    with ``override`` keys merged on top.
    """
    snapshot = await _get_latest_snapshot(db, dra_type, instance_label, "RBAR")

    if not snapshot:
        logger.debug("No RBAR snapshot for %s %s – using override only", dra_type, instance_label)
        return dict(override or {})

    rows = (
        await db.execute(
            select(RbarDumpRow).where(RbarDumpRow.snapshot_id == snapshot.id).limit(1)
        )
    ).scalars().all()

    if rows:
        base = dict(rows[0].raw_payload or {})
        base.update(override or {})
        return base

    return dict(override or {})
