from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.deps import get_db
from app.models.change_request import ChangeRequest
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.unknown_entry import UnknownEntry
from app.models.notification import Notification
from app.models.enums import RequestStatus, ImplStatus
from app.api.deps.auth import get_current_user
from app.core.cache import (
    cache_get, cache_set, cache_delete,
    TTL_DASHBOARD_SUMMARY, TTL_DASHBOARD_ANALYTICS,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
IST = ZoneInfo("Asia/Kolkata")


@router.get("/summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Overall system dashboard counts."""
    cached = cache_get("dashboard:summary")
    if cached:
        return cached
    total_requests = (await db.execute(select(func.count(ChangeRequest.id)))).scalar()

    status_counts = {}
    for status in RequestStatus:
        cnt = (await db.execute(
            select(func.count(ChangeRequest.id)).where(ChangeRequest.status == status.value)
        )).scalar()
        status_counts[status.value] = cnt

    pending_impl = (await db.execute(
        select(func.count(EntryInstanceStatus.id)).where(
            EntryInstanceStatus.impl_status == ImplStatus.PENDING.value
        )
    )).scalar()

    not_impl = (await db.execute(
        select(func.count(EntryInstanceStatus.id)).where(
            EntryInstanceStatus.impl_status == ImplStatus.AWAITING_IMPLEMENTATION.value
        )
    )).scalar()

    unknown_count = (await db.execute(
        select(func.count(UnknownEntry.id)).where(UnknownEntry.is_acknowledged == False)
    )).scalar()

    unread_notif = (await db.execute(
        select(func.count(Notification.id)).where(Notification.is_read == False)
    )).scalar()

    # Recent requests (last 10)
    recent = (await db.execute(
        select(ChangeRequest).order_by(ChangeRequest.created_at.desc()).limit(10)
    )).scalars().all()

    result = {
        "total_requests": total_requests,
        "status_counts": status_counts,
        "pending_implementation": pending_impl,
        "AWAITING_IMPLEMENTATION": not_impl,
        "unknown_entries": unknown_count,
        "unread_notifications": unread_notif,
        "recent_requests": [
            {
                "id": r.id,
                "status": r.status,
                "module": r.module,
                "uploaded_file_name": r.uploaded_file_name,
                "total_rows": r.total_rows,
                "processed_rows": r.processed_rows,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in recent
        ],
    }
    cache_set("dashboard:summary", result, TTL_DASHBOARD_SUMMARY)
    return result


@router.get("/analytics")
async def analytics(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Management analytics: avg implementation time, top sites, trends."""
    since = datetime.now(IST) - timedelta(days=days)

    # Requests over time (grouped by day)
    requests_over_time = (await db.execute(
        text("""
            SELECT
                DATE(created_at AT TIME ZONE 'Asia/Kolkata') AS day,
                COUNT(*) AS count
            FROM change_requests
            WHERE created_at >= :since
            GROUP BY day
            ORDER BY day
        """),
        {"since": since},
    )).fetchall()

    # Average implementation time by site (from entry_instance_statuses)
    avg_impl_time = (await db.execute(
        text("""
            SELECT
                SPLIT_PART(instance_label, '-', 1) AS site,
                AVG(
                    EXTRACT(EPOCH FROM (last_reconciled_at - created_at)) / 3600
                ) AS avg_hours
            FROM entry_instance_statuses
            WHERE impl_status = 'IMPLEMENTED'
              AND last_reconciled_at IS NOT NULL
              AND created_at >= :since
            GROUP BY site
            ORDER BY avg_hours DESC
        """),
        {"since": since},
    )).fetchall()

    # Pending count by site
    pending_by_site = (await db.execute(
        text("""
            SELECT
                SPLIT_PART(instance_label, '-', 1) AS site,
                COUNT(*) AS count
            FROM entry_instance_statuses
            WHERE impl_status = 'PENDING FOR RECONCILIATION'
            GROUP BY site
            ORDER BY count DESC
        """)
    )).fetchall()

    # Unknown entries by instance
    unknowns_by_instance = (await db.execute(
        text("""
            SELECT dra_type, instance_label, COUNT(*) AS count
            FROM unknown_entries
            WHERE is_acknowledged = false
            GROUP BY dra_type, instance_label
            ORDER BY count DESC
            LIMIT 20
        """)
    )).fetchall()

    return {
        "period_days": days,
        "requests_over_time": [
            {"day": str(r.day), "count": r.count} for r in requests_over_time
        ],
        "avg_implementation_hours_by_site": [
            {"site": r.site, "avg_hours": round(float(r.avg_hours or 0), 1)}
            for r in avg_impl_time
        ],
        "pending_by_site": [
            {"site": r.site, "count": r.count} for r in pending_by_site
        ],
        "unknown_entries_by_instance": [
            {"dra_type": r.dra_type, "instance_label": r.instance_label, "count": r.count}
            for r in unknowns_by_instance
        ],
    }


@router.get("/unknown-entries")
async def unknown_entries(
    acknowledged: bool = False,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = (
        select(UnknownEntry)
        .where(UnknownEntry.is_acknowledged == acknowledged)
        .order_by(UnknownEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    entries = (await db.execute(query)).scalars().all()
    total = (await db.execute(
        select(func.count(UnknownEntry.id)).where(UnknownEntry.is_acknowledged == acknowledged)
    )).scalar()

    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "dra_type": e.dra_type,
                "instance_label": e.instance_label,
                "entry_type": e.entry_type,
                "identifier": e.identifier,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


@router.patch("/unknown-entries/{entry_id}/acknowledge")
async def acknowledge_unknown(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    entry = (await db.execute(
        select(UnknownEntry).where(UnknownEntry.id == entry_id)
    )).scalars().first()
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(404, "Unknown entry not found")
    entry.is_acknowledged = True
    return {"id": entry_id, "acknowledged": True}
