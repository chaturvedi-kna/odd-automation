import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import aiofiles

from app.db.deps import get_db
from app.models.dump_snapshot import DumpSnapshot
from app.api.deps.auth import require_operator, get_current_user
from app.core.config import settings

router = APIRouter(prefix="/dumps", tags=["dumps"])

DUMP_UPLOAD_DIR = Path("/tmp/odd_dumps")
DUMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/ingest")
async def ingest_dump_file(
    file: UploadFile = File(...),
    dra_type: str = Form(...),
    instance_label: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator),
):
    """Upload a dump CSV and queue it for ingestion."""
    dest_path = DUMP_UPLOAD_DIR / file.filename

    async with aiofiles.open(dest_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Dispatch Celery task
    from app.workers.tasks import ingest_dump
    task = ingest_dump.delay(
        str(dest_path),
        dra_type,
        instance_label,
        file.filename,
    )

    return {
        "task_id": task.id,
        "message": f"Dump '{file.filename}' queued for ingestion",
        "dra_type": dra_type,
        "instance_label": instance_label,
    }


@router.post("/reconcile")
async def trigger_reconciliation(
    dra_type: str | None = None,
    instance_label: str | None = None,
    _=Depends(require_operator),
):
    """Manually trigger reconciliation (optionally for one instance)."""
    from app.workers.tasks import task_run_reconciliation
    task = task_run_reconciliation.delay(dra_type, instance_label)
    return {"task_id": task.id, "message": "Reconciliation queued"}


@router.get("/snapshots")
async def list_snapshots(
    dra_type: str | None = None,
    instance_label: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = select(DumpSnapshot).order_by(DumpSnapshot.created_at.desc())
    if dra_type:
        query = query.where(DumpSnapshot.dra_type == dra_type)
    if instance_label:
        query = query.where(DumpSnapshot.instance_label == instance_label)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    snapshots = result.scalars().all()
    return [
        {
            "id": s.id,
            "dra_type": s.dra_type,
            "instance_label": s.instance_label,
            "object_type": s.object_type,
            "file_name": s.file_name,
            "source_timestamp": s.source_timestamp.isoformat() if s.source_timestamp else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in snapshots
    ]
