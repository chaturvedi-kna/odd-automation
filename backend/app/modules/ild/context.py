import logging
from sqlalchemy import select, and_
from intervaltree import IntervalTree, Interval 

from app.models.dump_snapshot import DumpSnapshot
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.enums import ImplStatus, DecisionType

logger = logging.getLogger(__name__)

_ADD_DECISIONS = {
    DecisionType.ADD.value,
    DecisionType.DEPENDENCY_ADD.value,
    DecisionType.SUPERSEDE.value,
}
_DELETE_DECISIONS = {
    DecisionType.DELETE.value,
    DecisionType.DEPENDENCY_DELETE.value,
    DecisionType.SUPERSEDE_PENDING.value,
}


class InstanceContext:
    def __init__(self):
        # ── PRR State ─────────────────────────────────────────────────────
        self.prr_realms: set = set()
        self.prr_rules: set = set()
        
        self.prr_pending_realms: dict = {} # realm_lower → list[dict]

        # ── RBAR State ─────────────────────────────────────────────────────
        self.rbar_ranges = IntervalTree()  
        self.rbar_pending_tree = IntervalTree()  

    @staticmethod
    def _get_target_statuses():
        """Helper to track active funnel/pipeline validation states."""
        return [ImplStatus.PENDING.value, ImplStatus.AWAITING_IMPLEMENTATION.value]

    @staticmethod
    def _get_action(decision: str) -> str | None:
        """Helper to map decision types to absolute actions."""
        if decision in _ADD_DECISIONS:
            return "ADD"
        if decision in _DELETE_DECISIONS:
            return "DELETE"
        return None

    @staticmethod
    async def load(db, dra_type: str, instance_label: str) -> "InstanceContext":
        ctx = InstanceContext()
        target_statuses = InstanceContext._get_target_statuses()

        # ── 1. Load latest PRR dump snapshot ──────────────────────────────
        prr_snapshot = (
            await db.execute(
                select(DumpSnapshot)
                .where(
                    and_(
                        DumpSnapshot.dra_type == dra_type,
                        DumpSnapshot.instance_label == instance_label,
                        DumpSnapshot.object_type == "PRR",
                    )
                )
                .order_by(DumpSnapshot.created_at.desc())
                .limit(1)
            )
        ).scalars().first()

        if prr_snapshot:
            rows = (
                await db.execute(
                    select(PrrDumpRow).where(PrrDumpRow.snapshot_id == prr_snapshot.id)
                )
            ).scalars().all()
            for r in rows:
                if r.realm:
                    ctx.prr_realms.add(r.realm.lower())
                if r.name:
                    ctx.prr_rules.add(r.name.lower())

        # ── 2. Load latest RBAR dump snapshot ─────────────────────────────
        rbar_snapshot = (
            await db.execute(
                select(DumpSnapshot)
                .where(
                    and_(
                        DumpSnapshot.dra_type == dra_type,
                        DumpSnapshot.instance_label == instance_label,
                        DumpSnapshot.object_type == "RBAR",
                    )
                )
                .order_by(DumpSnapshot.created_at.desc())
                .limit(1)
            )
        ).scalars().first()

        if rbar_snapshot:
            rows = (
                await db.execute(
                    select(RbarDumpRow).where(RbarDumpRow.snapshot_id == rbar_snapshot.id)
                )
            ).scalars().all()
            for r in rows:
                if r.start_addr is not None and r.end_addr is not None:
                    ctx.rbar_ranges.add(Interval(int(r.start_addr), int(r.end_addr) + 1))

        # ── 3. Load PENDING/AWAITING_IMPLEMENTATION PRR changes (Chronological) ───
        prr_pending_rows = (
            await db.execute(
                select(EntryInstanceStatus, EntryInstanceDetail, PrrEntry)
                .join(
                    EntryInstanceDetail,
                    EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id,
                )
                .join(PrrEntry, PrrEntry.id == EntryInstanceStatus.entry_id)
                .where(
                    and_(
                        EntryInstanceStatus.dra_type == dra_type,
                        EntryInstanceStatus.instance_label == instance_label,
                        EntryInstanceStatus.entry_type == "PRR",
                        EntryInstanceStatus.impl_status.in_(target_statuses),
                    )
                )
                .order_by(
                    EntryInstanceStatus.created_at.asc(), 
                    EntryInstanceStatus.id.asc()
                ) 
            )
        ).all()

        for status, detail, entry in prr_pending_rows:
            if not detail.realm:
                continue
            
            realm_key = detail.realm.lower()
            action = InstanceContext._get_action(status.decision)
            if not action:
                continue

            # FIX: Append to a list structure instead of overwriting the map key
            if realm_key not in ctx.prr_pending_realms:
                ctx.prr_pending_realms[realm_key] = []
            
            ctx.prr_pending_realms[realm_key].append({
                "action": action,
                "request_id": entry.request_id,
                "rule": detail.final_prt_rule.lower() if detail.final_prt_rule else None
            })

            if action == "ADD":
                ctx.prr_realms.add(realm_key)
                if detail.final_prt_rule:
                    ctx.prr_rules.add(detail.final_prt_rule.lower())
            elif action == "DELETE":
                ctx.prr_realms.discard(realm_key)
                if detail.final_prt_rule:
                    ctx.prr_rules.discard(detail.final_prt_rule.lower())

        # ── 4. Load PENDING/AWAITING_IMPLEMENTATION RBAR changes (Chronological) ──
        rbar_pending_rows = (
            await db.execute(
                select(EntryInstanceStatus, EntryInstanceDetail, RbarEntry)
                .join(
                    EntryInstanceDetail,
                    EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id,
                )
                .join(RbarEntry, RbarEntry.id == EntryInstanceStatus.entry_id)
                .where(
                    and_(
                        EntryInstanceStatus.dra_type == dra_type,
                        EntryInstanceStatus.instance_label == instance_label,
                        EntryInstanceStatus.entry_type == "RBAR",
                        EntryInstanceStatus.impl_status.in_(target_statuses),
                    )
                )
                .order_by(
                    EntryInstanceStatus.created_at.asc(), 
                    EntryInstanceStatus.id.asc()
                ) 
            )
        ).all()

        for status, detail, entry in rbar_pending_rows:
            if detail.start_addr is None or detail.end_addr is None:
                continue
            
            start_val = int(detail.start_addr)
            end_val = int(detail.end_addr)
            action = InstanceContext._get_action(status.decision)
            if not action:
                continue

            ctx.rbar_pending_tree.add(Interval(
                start_val, 
                end_val + 1, 
                {"action": action, "request_id": entry.request_id}
            ))

            target_interval = Interval(start_val, end_val + 1)
            if action == "ADD":
                ctx.rbar_ranges.add(target_interval)
            elif action == "DELETE":
                for iv in list(ctx.rbar_ranges.overlap(start_val, end_val + 1)):
                    if iv.begin == start_val and iv.end == end_val + 1:
                        ctx.rbar_ranges.discard(iv)
                        break

        logger.debug(
            "Context completely loaded for %s %s: %d PRR realms, %d RBAR active intervals, %d RBAR pipeline intervals indexed, %d PRR pending items",
            dra_type, instance_label, len(ctx.prr_realms), len(ctx.rbar_ranges), len(ctx.rbar_pending_tree), sum(len(v) for v in ctx.prr_pending_realms.values())
        )
        return ctx