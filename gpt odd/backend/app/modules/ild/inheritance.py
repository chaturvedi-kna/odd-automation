from sqlalchemy import select, and_
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.dump_snapshot import DumpSnapshot


async def get_latest_snapshot(db, dra_type, instance_label, obj_type):
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
        )
    ).scalars().first()


async def inherit_prr_config(db, dra_type, instance_label, realm, override=None):
    snapshot = await get_latest_snapshot(db, dra_type, instance_label, "PRR")

    if not snapshot:
        return override or {}

    rows = (
        await db.execute(
            select(PrrDumpRow).where(PrrDumpRow.snapshot_id == snapshot.id)
        )
    ).scalars().all()

    # 2️⃣ Fallback → latest row template
    if rows:
        return {**(rows[0].raw_payload or {}), **(override or {})}

    return override or {}


async def inherit_rbar_config(db, dra_type, instance_label, start, end, override=None):
    snapshot = await get_latest_snapshot(db, dra_type, instance_label, "RBAR")

    if not snapshot:
        return override or {}

    rows = (
        await db.execute(
            select(RbarDumpRow).where(RbarDumpRow.snapshot_id == snapshot.id)
        )
    ).scalars().all()

    # fallback
    if rows:
        return {**(rows[0].raw_payload or {}), **(override or {})}

    return override or {}