from sqlalchemy import select, and_
from app.models.dump_snapshot import DumpSnapshot
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail


class InstanceContext:
    def __init__(self):
        self.prr_realms = set()
        self.prr_rules = set()

        self.rbar_ranges = []  # (start, end)

        self.pending_map = {}  # key → (action, request_id)

    @staticmethod
    async def load(db, dra_type, instance_label):
        ctx = InstanceContext()

        # ---------- LOAD DUMP ----------
        snapshot = (
            await db.execute(
                select(DumpSnapshot)
                .where(
                    and_(
                        DumpSnapshot.dra_type == dra_type,
                        DumpSnapshot.instance_label == instance_label,
                    )
                )
                .order_by(DumpSnapshot.created_at.desc())
            )
        ).scalars().first()

        if snapshot:
            if snapshot.object_type == "PRR":
                rows = (
                    await db.execute(
                        select(PrrDumpRow).where(
                            PrrDumpRow.snapshot_id == snapshot.id
                        )
                    )
                ).scalars().all()

                for r in rows:
                    if r.realm:
                        ctx.prr_realms.add(r.realm.lower())
                    if r.name:
                        ctx.prr_rules.add(r.name.lower())

            if snapshot.object_type == "RBAR":
                rows = (
                    await db.execute(
                        select(RbarDumpRow).where(
                            RbarDumpRow.snapshot_id == snapshot.id
                        )
                    )
                ).scalars().all()

                for r in rows:
                    if r.start_addr and r.end_addr:
                        ctx.rbar_ranges.append((int(r.start_addr), int(r.end_addr)))

        # ---------- LOAD PENDING ----------
        statuses = (
            await db.execute(
                select(EntryInstanceStatus).where(
                    and_(
                        EntryInstanceStatus.dra_type == dra_type,
                        EntryInstanceStatus.instance_label == instance_label,
                    )
                )
            )
        ).scalars().all()

        for s in statuses:
            detail = (
                await db.execute(
                    select(EntryInstanceDetail).where(
                        EntryInstanceDetail.instance_status_id == s.id
                    )
                )
            ).scalars().first()

            if not detail:
                continue

            key = None

            if s.entry_type == "PRR":
                key = detail.realm.lower()
                ctx.prr_realms.add(key)

            elif s.entry_type == "RBAR":
                key = (detail.start_addr, detail.end_addr)
                ctx.rbar_ranges.append(key)

            if key:
                ctx.pending_map[key] = (
                    s.impl_status,
                    s.entry_id,
                )

        return ctx