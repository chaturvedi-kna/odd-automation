import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload

from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.entry_instance_relationship import EntryInstanceRelationship
from app.models.audit_log import AuditLog
from app.models.unknown_entry import UnknownEntry
from app.models.enums import ImplStatus, DecisionType
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.dump_snapshot import DumpSnapshot
from app.modules.ild.unknown_detector import detect_unknown_prr, detect_unknown_rbar

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _ist_now() -> datetime:
    return datetime.now(IST)


def _decision_is_add(decision: str) -> bool:
    return decision in (DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value)


def _decision_is_delete(decision: str) -> bool:
    return decision in (
        DecisionType.DELETE.value,
        DecisionType.DEPENDENCY_DELETE.value,
        DecisionType.SUPERSEDE.value
    )


def _decision_is_supersede_pending(decision: str) -> bool:
    return decision == DecisionType.SUPERSEDE_PENDING.value


def _are_dependencies_satisfied(db: Session, status_id: str) -> bool:
    """
    Renamed and optimized dependency constraint check.
    Ensures downstream requests stay locked in queue until upstream blockers clear out.
    """
    relationships = db.execute(
        select(EntryInstanceRelationship).where(EntryInstanceRelationship.instance_status_id == status_id)
    ).scalars().all()

    if not relationships:
        return True

    for rel in relationships:
        parent_status = db.execute(
            select(EntryInstanceStatus).where(
                and_(
                    EntryInstanceStatus.request_id == rel.related_request_id,
                    EntryInstanceStatus.impl_status.in_([ImplStatus.PENDING.value, ImplStatus.AWAITING_IMPLEMENTATION.value])
                )
            )
        ).scalars().first()
        
        if parent_status:
            return False
            
    return True


def _reconcile_prr(s: EntryInstanceStatus, detail: EntryInstanceDetail, prr_snapshot_map: dict[str, str]) -> bool:
    realm = (detail.realm or "").lower()
    expected_rule = (detail.final_prt_rule or "").lower()
    actual_rule = prr_snapshot_map.get(realm)

    if _decision_is_add(s.decision):
        return actual_rule == expected_rule if expected_rule else realm in prr_snapshot_map
    elif _decision_is_delete(s.decision):
        return realm not in prr_snapshot_map
    elif _decision_is_supersede_pending(s.decision):
        return actual_rule == expected_rule

    return False


def _reconcile_rbar(s: EntryInstanceStatus, detail: EntryInstanceDetail, rbar_ranges_set: set[tuple]) -> bool:
    if detail.start_addr is None or detail.end_addr is None:
        return False
        
    dest = (detail.raw_payload.get("destination") or "").strip().lower() if detail.raw_payload else ""
    rk = (int(detail.start_addr), int(detail.end_addr), dest)

    if _decision_is_add(s.decision) or _decision_is_supersede_pending(s.decision):
        return rk in rbar_ranges_set
    elif _decision_is_delete(s.decision):
        return rk not in rbar_ranges_set

    return False


def run_reconciliation(db: Session, dra_type: str | None = None, instance_label: str | None = None):
    implemented = awaiting_implementation = unknown_count = 0
    now = _ist_now()

    filters = [EntryInstanceStatus.impl_status.in_([ImplStatus.PENDING.value, ImplStatus.AWAITING_IMPLEMENTATION.value])]
    if dra_type:
        filters.append(EntryInstanceStatus.dra_type == dra_type)
    if instance_label:
        filters.append(EntryInstanceStatus.instance_label == instance_label)

    statuses = db.execute(
        select(EntryInstanceStatus).options(joinedload(EntryInstanceStatus.details)).where(and_(*filters))
    ).scalars().all()

    by_instance: dict[tuple, list] = {}
    for s in statuses:
        key = (s.dra_type, s.instance_label)
        by_instance.setdefault(key, []).append(s)

    for (inst_dra, inst_label), inst_statuses in by_instance.items():
        try:
            prr_snap = _latest_snapshot(db, inst_dra, inst_label, "PRR")
            rbar_snap = _latest_snapshot(db, inst_dra, inst_label, "RBAR")

            prr_snapshot_map: dict[str, str] = {}
            rbar_ranges_set: set[tuple] = set()

            if prr_snap:
                rows = db.execute(select(PrrDumpRow).where(PrrDumpRow.snapshot_id == prr_snap.id)).scalars().all()
                prr_snapshot_map = {r.realm.lower(): (r.name or "").lower() for r in rows if r.realm}

            if rbar_snap:
                rows = db.execute(select(RbarDumpRow).where(RbarDumpRow.snapshot_id == rbar_snap.id)).scalars().all()
                rbar_ranges_set = {
                    (int(r.start_addr), int(r.end_addr), (r.destination or "").strip().lower())
                    for r in rows if r.start_addr is not None and r.end_addr is not None
                }

            for s in inst_statuses:
                s.last_reconciled_at = now
                
                detail = s.details[0] if s.details else None
                if not detail:
                    detail = db.execute(select(EntryInstanceDetail).where(EntryInstanceDetail.instance_status_id == s.id)).scalars().first()

                if not detail:
                    continue

                # Swapped to the newly renamed dependency compliance function
                if not _are_dependencies_satisfied(db, s.id):
                    s.impl_status = ImplStatus.AWAITING_IMPLEMENTATION.value
                    awaiting_implementation += 1
                    continue

                if s.entry_type == "PRR":
                    is_impl = _reconcile_prr(s, detail, prr_snapshot_map)
                elif s.entry_type == "RBAR":
                    is_impl = _reconcile_rbar(s, detail, rbar_ranges_set)
                else:
                    is_impl = False

                new_status = ImplStatus.IMPLEMENTED.value if is_impl else ImplStatus.AWAITING_IMPLEMENTATION.value
                
                if s.impl_status != new_status:
                    s.impl_status = new_status
                    db.add(AuditLog(
                        level="INFO",
                        entry_type=s.entry_type,
                        message=f"Reconciled state mutation {s.entry_type} item {s.entry_id} -> {new_status}",
                        instance_label=inst_label,
                        dra_type=inst_dra,
                    ))
                
                if is_impl:
                    implemented += 1
                else:
                    awaiting_implementation += 1

            # ── Unknown entry detection ──────────────────
            if prr_snap:
                existing_unknowns = db.execute(select(UnknownEntry.realm).where(UnknownEntry.snapshot_id == prr_snap.id)).scalars().all()
                existing_set = {r.lower() for r in existing_unknowns if r}

                unknowns = detect_unknown_prr(db, inst_dra, inst_label, prr_snap)
                for u in unknowns:
                    if u.realm and u.realm.lower() in existing_set:
                        continue
                    db.add(u)
                    unknown_count += 1

            if rbar_snap:
                unknowns = detect_unknown_rbar(db, inst_dra, inst_label, rbar_snap)
                for u in unknowns:
                    if db.execute(select(UnknownEntry).where(and_(UnknownEntry.snapshot_id == rbar_snap.id, UnknownEntry.start_addr == u.start_addr, UnknownEntry.end_addr == u.end_addr))).scalars().first():
                        continue
                    db.add(u)
                    unknown_count += 1

            db.flush()  # Push mutations to transaction staging area cleanly without calling commit yet

        except Exception as ex:
            logger.exception("Reconciliation block failure on cluster %s|%s: %s", inst_dra, inst_label, ex)
            db.add(AuditLog(
                level="ERROR",
                entry_type="INSTANCE",
                message=f"Reconciliation runtime exception on {inst_label}: {ex}",
                instance_label=inst_label,
                dra_type=inst_dra,
            ))
            db.flush()

    # Commit everything at once at the very tail end of the function execution graph
    db.commit()

    # Restored metrics summary tracking telemetry log
    logger.info(
        "Reconciliation done: %d implemented, %d awaiting implementation, %d unknown entries detected.",
        implemented, awaiting_implementation, unknown_count,
    )

    return {
        "implemented": implemented,
        "AWAITING_IMPLEMENTATION": awaiting_implementation,
        "unknown_entries": unknown_count,
    }


def _latest_snapshot(db: Session, dra_type: str, instance_label: str, obj_type: str):
    return db.execute(
        select(DumpSnapshot)
        .where(and_(DumpSnapshot.dra_type == dra_type, DumpSnapshot.instance_label == instance_label, DumpSnapshot.object_type == obj_type))
        .order_by(DumpSnapshot.created_at.desc())
        .limit(1)
    ).scalars().first()