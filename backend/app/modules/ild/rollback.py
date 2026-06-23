"""
Rollback orchestration.

Creates a new ChangeRequest that inverts all IMPLEMENTED entries from a
completed request.  Only IMPLEMENTED entries are rolled back; PENDING or
AWAITING_IMPLEMENTATION ones are left as-is (they have not reached the DRA yet).

For each IMPLEMENTED:
  - ADD decision  → new DELETE entry on same instance
  - DELETE decision → new ADD entry on same instance
  - SUPERSEDE → new DELETE of the new range + re-ADD the old range
"""
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_request import ChangeRequest
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.enums import (
    RequestStatus, DecisionType, ImplStatus, ActionType
)
from app.core.cache import invalidate_dashboard

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

ADD_DECISIONS = {
    DecisionType.ADD.value,
    DecisionType.DEPENDENCY_ADD.value,
    DecisionType.SUPERSEDE.value,
}
DELETE_DECISIONS = {
    DecisionType.DELETE.value,
    DecisionType.DEPENDENCY_DELETE.value,
}


async def create_rollback_request(
    db: AsyncSession,
    original_request_id: str,
    requested_by_user_id: str,
) -> ChangeRequest:
    """
    Inspect all IMPLEMENTED statuses from *original_request_id* and build an
    inverse ChangeRequest.  Returns the new ChangeRequest (not yet committed).
    """
    # ── Validate original request ──────────────────────────────────────────
    original = (await db.execute(
        select(ChangeRequest).where(ChangeRequest.id == original_request_id)
    )).scalars().first()

    if not original:
        raise ValueError(f"Request {original_request_id} not found")

    if original.status not in (RequestStatus.DONE.value, RequestStatus.DONE_PARTIAL.value):
        raise ValueError(
            f"Cannot rollback request in status '{original.status}'. "
            "Only DONE or DONE_PARTIAL requests can be rolled back."
        )

    # ── Gather IMPLEMENTED statuses ────────────────────────────────────────
    implemented = (await db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(
            EntryInstanceDetail,
            EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id,
        )
        .join(PrrEntry, PrrEntry.id == EntryInstanceStatus.entry_id, isouter=True)
        .where(
            and_(
                EntryInstanceStatus.impl_status == ImplStatus.IMPLEMENTED.value,
            )
        )
    )).all()

    # Filter to entries that belong to the original request
    original_prr_ids = {
        e.id for e in (await db.execute(
            select(PrrEntry.id).where(PrrEntry.request_id == original_request_id)
        )).scalars().all()
    }
    original_rbar_ids = {
        e.id for e in (await db.execute(
            select(RbarEntry.id).where(RbarEntry.request_id == original_request_id)
        )).scalars().all()
    }

    eligible = [
        (s, d) for s, d in implemented
        if (
            (s.entry_type == "PRR" and s.entry_id in original_prr_ids)
            or (s.entry_type == "RBAR" and s.entry_id in original_rbar_ids)
        )
    ]

    if not eligible:
        raise ValueError("No IMPLEMENTED entries found to roll back.")

    # ── Build rollback ChangeRequest ───────────────────────────────────────
    rollback_id = str(uuid.uuid4())
    selected_instances = list({
        f"{s.dra_type}|{s.instance_label}" for s, _ in eligible
    })
    selected_instances_list = [
        {"dra_type": p.split("|")[0], "instance_label": p.split("|")[1]}
        for p in selected_instances
    ]

    rollback_req = ChangeRequest(
        id=rollback_id,
        module=original.module,
        status=RequestStatus.PROCESSING.value,
        uploaded_file_name=f"rollback_of_{original_request_id[:8]}",
        created_by_user_id=requested_by_user_id,
        selected_instances=selected_instances_list,
        total_rows=len(eligible),
    )
    db.add(rollback_req)
    await db.flush()

    processed = skipped = 0

    for status_row, detail in eligible:
        # Determine inverse action
        if status_row.decision in ADD_DECISIONS:
            inv_action = "DELETE"
        elif status_row.decision in DELETE_DECISIONS:
            inv_action = "ADD"
        else:
            skipped += 1
            continue

        inst = {"dra_type": status_row.dra_type, "instance_label": status_row.instance_label}

        if status_row.entry_type == "PRR":
            new_entry = PrrEntry(
                request_id=rollback_id,
                realm=detail.realm,
                prt_rule=detail.final_prt_rule,
                action=inv_action,
                raw_payload={
                    "rollback_of": status_row.entry_id,
                    "realm": detail.realm,
                    "action": inv_action,
                },
            )
            db.add(new_entry)
            await db.flush()

            new_status = EntryInstanceStatus(
                entry_id=new_entry.id,
                entry_type="PRR",
                dra_type=inst["dra_type"],
                instance_label=inst["instance_label"],
                decision=DecisionType.DELETE.value if inv_action == "DELETE" else DecisionType.ADD.value,
                reason=f"Rollback of request {original_request_id[:8]}",
                impl_status=ImplStatus.PENDING.value,
            )
            db.add(new_status)
            await db.flush()

            db.add(EntryInstanceDetail(
                instance_status_id=new_status.id,
                entry_id=new_entry.id,
                entry_type="PRR",
                dra_type=inst["dra_type"],
                instance_label=inst["instance_label"],
                final_prt_rule=detail.final_prt_rule,
                realm=detail.realm,
                raw_payload={"rollback": True, "realm": detail.realm},
            ))

        elif status_row.entry_type == "RBAR":
            if detail.start_addr is None:
                skipped += 1
                continue

            new_entry = RbarEntry(
                request_id=rollback_id,
                realm=None,
                start_addr=int(detail.start_addr),
                end_addr=int(detail.end_addr),
                action=inv_action,
                raw_payload={
                    "rollback_of": status_row.entry_id,
                    "start_addr": int(detail.start_addr),
                    "end_addr": int(detail.end_addr),
                    "action": inv_action,
                },
            )
            db.add(new_entry)
            await db.flush()

            new_status = EntryInstanceStatus(
                entry_id=new_entry.id,
                entry_type="RBAR",
                dra_type=inst["dra_type"],
                instance_label=inst["instance_label"],
                decision=DecisionType.DELETE.value if inv_action == "DELETE" else DecisionType.ADD.value,
                reason=f"Rollback of request {original_request_id[:8]}",
                impl_status=ImplStatus.PENDING.value,
            )
            db.add(new_status)
            await db.flush()

            db.add(EntryInstanceDetail(
                instance_status_id=new_status.id,
                entry_id=new_entry.id,
                entry_type="RBAR",
                dra_type=inst["dra_type"],
                instance_label=inst["instance_label"],
                start_addr=int(detail.start_addr),
                end_addr=int(detail.end_addr),
                destination=detail.destination,
                raw_payload={"rollback": True},
            ))

        processed += 1

        db.add(AuditLog(
            request_id=rollback_id,
            level="INFO",
            entry_type=status_row.entry_type,
            message=(
                f"Rollback entry created: {inv_action} "
                f"{'realm=' + detail.realm if status_row.entry_type == 'PRR' else str(detail.start_addr) + '-' + str(detail.end_addr)}"
            ),
            instance_label=inst["instance_label"],
            dra_type=inst["dra_type"],
        ))

    rollback_req.processed_rows = processed
    rollback_req.skipped_rows = skipped
    rollback_req.status = RequestStatus.DONE.value
    rollback_req.completed_at = datetime.now(IST)

    # Notify
    db.add(Notification(
        type="ROLLBACK",
        message=(
            f"Rollback request created for {original_request_id[:8]}: "
            f"{processed} entries queued for reversal."
        ),
        related_request_id=rollback_id,
    ))

    invalidate_dashboard()

    logger.info(
        "Rollback request %s created from %s: %d entries, %d skipped",
        rollback_id, original_request_id, processed, skipped,
    )
    return rollback_req
