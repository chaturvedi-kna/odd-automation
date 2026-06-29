import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_request import ChangeRequest
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_relationship import EntryInstanceRelationship
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.enums import RequestStatus, ImplStatus
from app.core.cache import invalidate_dashboard

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _ist_now() -> datetime:
    return datetime.now(IST)


async def rollback_pending_request(
    db: AsyncSession,
    original_request_id: str,
    requested_by_user_id: str,
) -> ChangeRequest:
    """
    Administrative Cancel/Rollback:
    Safely aborts in-flight requests, flushes active dependency networks, 
    and verifies if downstream blockers are truly active before denying an abort.
    """
    now = _ist_now()
    
    try:
        # ── 1. Fetch and Validate Original Request ─────────────────────────
        original = (await db.execute(
            select(ChangeRequest).where(ChangeRequest.id == original_request_id)
        )).scalars().first()

        if not original:
            raise ValueError(f"Request {original_request_id} not found")

        if original.status in (
            RequestStatus.COMPLETED.value,
            RequestStatus.FAILED.value,
            RequestStatus.ROLLEDBACK.value
        ):
            raise ValueError(
                f"Cannot abort request {original_request_id[:8]} because it is already in a terminal "
                f"'{original.status}' state."
            )

        # ── 2. GUARDRAIL: Verify Active Downstream Dependents Only ─────────
        # Join against EntryInstanceStatus to verify if downstream dependents are still active blockers.
        active_blocker_check = (await db.execute(
            select(EntryInstanceRelationship)
            .join(
                EntryInstanceStatus, 
                EntryInstanceStatus.id == EntryInstanceRelationship.instance_status_id
            )
            .where(
                and_(
                    EntryInstanceRelationship.related_request_id == original_request_id,
                    EntryInstanceStatus.impl_status.in_([
                        ImplStatus.PENDING.value, 
                        ImplStatus.AWAITING_IMPLEMENTATION.value
                    ])
                )
            )
        )).scalars().first()

        if active_blocker_check:
            raise ValueError(
                f"Rollback Denied: Request {original_request_id[:8]} cannot be cancelled because "
                "active downstream pending requests currently depend on its execution. Cancel those dependent requests first."
            )

        # ── 3. Gather In-Flight Pipeline Status Records ────────────────────
        result = await db.execute(
            select(EntryInstanceStatus).where(
                and_(
                    EntryInstanceStatus.request_id == original_request_id,
                    EntryInstanceStatus.impl_status.in_([
                        ImplStatus.PENDING.value, 
                        ImplStatus.AWAITING_IMPLEMENTATION.value
                    ])
                )
            )
        )
        active_statuses = result.scalars().all()

        if not active_statuses:
            raise ValueError("No pending or awaiting implementation entries found to abort for this request.")

        status_ids = [status.id for status in active_statuses]
        cancelled_count = 0

        for status in active_statuses:
            status.impl_status = ImplStatus.CANCELLED.value  
            status.reason = f"Cancelled before implementation by user {requested_by_user_id}."
            status.last_reconciled_at = now
            
            db.add(status)
            cancelled_count += 1

            # FIX: AuditLog level changed from WARNING to INFO for standardized tracking
            db.add(AuditLog(
                request_id=original_request_id,
                level="INFO", 
                entry_type=status.entry_type,
                message=f"Request {original_request_id[:8]} cancelled by user {requested_by_user_id} before implementation.",
                instance_label=status.instance_label,
                dra_type=status.dra_type,
            ))

        # ── 4. Purge All Associated Relationships (Allowed Paths) ─────────
        # Clear out linkages where this request was waiting on an upstream blocker
        if status_ids:
            await db.execute(
                delete(EntryInstanceRelationship).where(
                    EntryInstanceRelationship.instance_status_id.in_(status_ids)
                )
            )

        # FIX: Restored cascading erasure of dead downstream dependency markers
        await db.execute(
            delete(EntryInstanceRelationship).where(
                EntryInstanceRelationship.related_request_id == original_request_id
            )
        )

        # ── 5. Update Request Status & Notification ────────────────────────
        original.status = RequestStatus.ROLLEDBACK.value  
        original.completed_at = now
        db.add(original)

        db.add(Notification(
            type="ROLLBACK",
            message=(
                f"Change Request {original_request_id[:8]} was cancelled before implementation by user {requested_by_user_id} "
                f"at {now.strftime('%Y-%m-%d %H:%M:%S')} IST. {cancelled_count} entries were purged from the queue."
            ),
            related_request_id=original_request_id,
        ))

        await db.flush()
        await db.commit()
        
        invalidate_dashboard()

        logger.info(
            "User %s successfully completed administrative rollback on request %s at %s. Purged %d queue items.",
            requested_by_user_id, original_request_id, now.isoformat(), cancelled_count
        )
        
        return original

    except Exception as ex:
        await db.rollback()
        logger.error(
            "Rollback transaction block execution failed for request %s (Initiated by User: %s): %s", 
            original_request_id, requested_by_user_id, ex
        )
        raise ex