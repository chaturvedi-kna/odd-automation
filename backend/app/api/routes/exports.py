import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.deps import get_db
from app.models.change_request import ChangeRequest
from app.api.deps.auth import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{request_id}/delta")
async def download_delta(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    req = (await db.execute(
        select(ChangeRequest).where(ChangeRequest.id == request_id)
    )).scalars().first()
    if not req:
        raise HTTPException(404, "Request not found")

    out_path = Path(settings.EXPORT_PATH) / f"delta_{request_id}.xlsx"

    # Generate in the sync threadpool (openpyxl is sync)
    import asyncio
    await asyncio.get_event_loop().run_in_executor(
        None, _generate_delta, request_id, str(out_path)
    )

    return FileResponse(
        path=str(out_path),
        filename=f"delta_{req.uploaded_file_name or request_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/{request_id}/master")
async def download_master_odd(
    request_id: str,
    dra_type: str,
    instance_label: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    out_path = Path(settings.EXPORT_PATH) / f"master_{dra_type}_{instance_label}.xlsx"

    import asyncio
    await asyncio.get_event_loop().run_in_executor(
        None, _generate_master, dra_type, instance_label, str(out_path)
    )

    return FileResponse(
        path=str(out_path),
        filename=f"ODD_master_{dra_type}_{instance_label}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _generate_delta(request_id: str, out_path: str):
    from app.db.session import SyncSessionLocal
    from app.modules.ild.exporter import delta_excel
    with SyncSessionLocal() as db:
        delta_excel(db, request_id, out_path)


def _generate_master(dra_type: str, instance_label: str, out_path: str):
    from app.db.session import SyncSessionLocal
    from app.modules.ild.exporter import master_odd_excel
    with SyncSessionLocal() as db:
        master_odd_excel(db, dra_type, instance_label, out_path)
