import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import aiofiles
import json

from app.db.deps import get_db
from app.models.change_request import ChangeRequest
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.audit_log import AuditLog
from app.models.enums import RequestStatus
from app.api.deps.auth import get_current_user, require_operator
from app.core.config import settings

router = APIRouter(prefix="/requests", tags=["requests"])

# Config-driven upload path (never hardcode paths); created lazily on first use
UPLOAD_DIR = Path(settings.UPLOAD_PATH)


@router.post("/")
async def create_request(
    file: UploadFile = File(...),
    module: str = Form(default="ILD"),
    selected_instances: str = Form(...),   # JSON string: [{dra_type, instance_label}, ...]
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_operator),
):
    try:
        instances = json.loads(selected_instances)
    except Exception:
        raise HTTPException(400, "selected_instances must be valid JSON")

    if not instances:
        raise HTTPException(400, "At least one instance must be selected")

    for inst in instances:
        if not isinstance(inst, dict) or "dra_type" not in inst or "instance_label" not in inst:
            raise HTTPException(
                400, "Each selected instance must contain dra_type and instance_label"
            )

    request_id = str(uuid.uuid4())
    csv_filename = f"{request_id}_{file.filename}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = UPLOAD_DIR / csv_filename

    # Save uploaded file
    async with aiofiles.open(csv_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Create DB record
    req = ChangeRequest(
        id=request_id,
        module=module,
        status=RequestStatus.QUEUED.value,
        uploaded_file_name=file.filename,
        created_by_user_id=current_user.id,
        selected_instances=instances,
    )
    db.add(req)
    await db.flush()
    await db.commit()

    # Dispatch Celery task
    from app.workers.tasks import task_process_request
    task_process_request.delay(request_id, str(csv_path), instances)

    return {
        "id": request_id,
        "status": RequestStatus.QUEUED.value,
        "module": module,
        "uploaded_file_name": file.filename,
    }


@router.get("/")
async def list_requests(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = select(ChangeRequest).order_by(ChangeRequest.created_at.desc())
    if status:
        query = query.where(ChangeRequest.status == status)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    requests = result.scalars().all()

    count_query = select(func.count(ChangeRequest.id))
    if status:
        count_query = count_query.where(ChangeRequest.status == status)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_req_summary(r) for r in requests],
    }


@router.get("/{request_id}")
async def get_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    req = (await db.execute(
        select(ChangeRequest).where(ChangeRequest.id == request_id)
    )).scalars().first()

    if not req:
        raise HTTPException(404, "Request not found")

    # Load entries summary
    prr_count = (await db.execute(
        select(func.count(PrrEntry.id)).where(PrrEntry.request_id == request_id)
    )).scalar()

    rbar_count = (await db.execute(
        select(func.count(RbarEntry.id)).where(RbarEntry.request_id == request_id)
    )).scalar()

    # Load audit logs
    audit_rows = (await db.execute(
        select(AuditLog)
        .where(AuditLog.request_id == request_id)
        .order_by(AuditLog.created_at.asc())
        .limit(500)
    )).scalars().all()

    # Load statuses grouped by instance
    statuses = (await db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id, isouter=True)
        .where(
            EntryInstanceStatus.entry_id.in_(
                select(PrrEntry.id).where(PrrEntry.request_id == request_id).union(
                    select(RbarEntry.id).where(RbarEntry.request_id == request_id)
                )
            )
        )
        .order_by(EntryInstanceStatus.created_at.asc())
        .limit(1000)
    )).all()

    return {
        **_req_summary(req),
        "prr_entries": prr_count,
        "rbar_entries": rbar_count,
        "audit_logs": [
            {
                "id": a.id,
                "level": a.level,
                "entry_type": a.entry_type,
                "message": a.message,
                "instance_label": a.instance_label,
                "dra_type": a.dra_type,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audit_rows
        ],
        "instance_statuses": [
            {
                "instance_label": s.instance_label,
                "dra_type": s.dra_type,
                "entry_type": s.entry_type,
                "decision": s.decision,
                "reason": s.reason,
                "impl_status": s.impl_status,
                "realm": d.realm if d else None,
                "final_prt_rule": d.final_prt_rule if d else None,
                "start_addr": str(d.start_addr) if d and d.start_addr else None,
                "end_addr": str(d.end_addr) if d and d.end_addr else None,
                "dependency_note": s.dependency_note,
            }
            for s, d in statuses
        ],
    }


def _req_summary(r: ChangeRequest) -> dict:
    return {
        "id": r.id,
        "module": r.module,
        "status": r.status,
        "uploaded_file_name": r.uploaded_file_name,
        "total_rows": r.total_rows,
        "processed_rows": r.processed_rows,
        "skipped_rows": r.skipped_rows,
        "failed_rows": r.failed_rows,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "selected_instances": getattr(r, "selected_instances", []),
    }
