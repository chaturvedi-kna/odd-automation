"""
Reconciliation engine.

For each PENDING EntryInstanceStatus, compare against the latest dump snapshot
and mark IMPLEMENTED or AWAITING_IMPLEMENTATION.

Also detects unknown entries: in-scope dump rows that do not correspond to any
ADD request we issued.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.dump_snapshot import DumpSnapshot
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.audit_log import AuditLog
from app.models.unknown_entry import UnknownEntry
from app.models.enums import ImplStatus, DecisionType
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
        DecisionType.SUPERSEDE.value,
    )


# ── Sync helpers (called from Celery task with sync session) ──────────────────

def run_reconciliation(db: Session, dra_type: str | None = None, instance_label: str | None = None):
    """
    Reconcile all PENDING statuses (optionally filtered to a single instance).
    Returns summary dict.
    """
    implemented = AWAITING_IMPLEMENTATION = unknown_count = 0
    now = _ist_now()

    # Build instance filter
    filters = [EntryInstanceStatus.impl_status == ImplStatus.PENDING.value]
    if dra_type:
        filters.append(EntryInstanceStatus.dra_type == dra_type)
    if instance_label:
        filters.append(EntryInstanceStatus.instance_label == instance_label)

    statuses = db.execute(select(EntryInstanceStatus).where(and_(*filters))).scalars().all()

    # Group by instance for efficient snapshot loading
    by_instance: dict[tuple, list] = {}
    for s in statuses:
        key = (s.dra_type, s.instance_label)
        by_instance.setdefault(key, []).append(s)

    for (inst_dra, inst_label), inst_statuses in by_instance.items():
        prr_snap = _latest_snapshot(db, inst_dra, inst_label, "PRR")
        rbar_snap = _latest_snapshot(db, inst_dra, inst_label, "RBAR")

        prr_realms: set[str] = set()
        rbar_ranges: set[tuple] = set()

        if prr_snap:
            rows = db.execute(
                select(PrrDumpRow).where(PrrDumpRow.snapshot_id == prr_snap.id)
            ).scalars().all()
            prr_realms = {r.realm.lower() for r in rows if r.realm}

        if rbar_snap:
            rows = db.execute(
                select(RbarDumpRow).where(RbarDumpRow.snapshot_id == rbar_snap.id)
            ).scalars().all()
            rbar_ranges = {
                (int(r.start_addr), int(r.end_addr))
                for r in rows
                if r.start_addr is not None and r.end_addr is not None
            }

        for s in inst_statuses:
            detail = db.execute(
                select(EntryInstanceDetail).where(
                    EntryInstanceDetail.instance_status_id == s.id
                )
            ).scalars().first()

            if not detail:
                continue

            is_impl = False

            if s.entry_type == "PRR":
                realm = (detail.realm or "").lower()
                if _decision_is_add(s.decision):
                    is_impl = realm in prr_realms
                elif _decision_is_delete(s.decision):
                    is_impl = realm not in prr_realms

            elif s.entry_type == "RBAR":
                rk = (int(detail.start_addr), int(detail.end_addr)) if detail.start_addr else None
                if rk:
                    if _decision_is_add(s.decision):
                        is_impl = rk in rbar_ranges
                    elif _decision_is_delete(s.decision):
                        is_impl = rk not in rbar_ranges

            new_status = ImplStatus.IMPLEMENTED.value if is_impl else ImplStatus.AWAITING_IMPLEMENTATION.value
            if s.impl_status != new_status:
                s.impl_status = new_status
                s.last_reconciled_at = now
                db.add(AuditLog(
                    level="INFO",
                    entry_type=s.entry_type,
                    message=f"Reconciled {s.entry_type} entry {s.entry_id} → {new_status}",
                    instance_label=inst_label,
                    dra_type=inst_dra,
                ))
            if is_impl:
                implemented += 1
            else:
                AWAITING_IMPLEMENTATION += 1

        # ── Unknown entry detection ────────────────────────────────────────
        if prr_snap:
            unknowns = detect_unknown_prr(db, inst_dra, inst_label, prr_snap)
            for u in unknowns:
                db.add(u)
                unknown_count += 1

        if rbar_snap:
            unknowns = detect_unknown_rbar(db, inst_dra, inst_label, rbar_snap)
            for u in unknowns:
                db.add(u)
                unknown_count += 1

    db.commit()
    logger.info(
        "Reconciliation done: %d implemented, %d not implemented, %d unknown entries",
        implemented, AWAITING_IMPLEMENTATION, unknown_count,
    )
    return {
        "implemented": implemented,
        "AWAITING_IMPLEMENTATION": AWAITING_IMPLEMENTATION,
        "unknown_entries": unknown_count,
    }


def _latest_snapshot(db: Session, dra_type: str, instance_label: str, obj_type: str):
    return db.execute(
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
    ).scalars().first()
