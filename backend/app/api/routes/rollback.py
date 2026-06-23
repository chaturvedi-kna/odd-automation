from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.deps import get_db
from app.models.change_request import ChangeRequest
from app.api.deps.auth import require_operator

router = APIRouter(prefix="/requests", tags=["rollback"])


@router.post("/{request_id}/rollback")
async def rollback_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_operator),
):
    """
    Create a rollback ChangeRequest that inverts all IMPLEMENTED entries
    from the given completed request.
    """
    from app.modules.ild.rollback import create_rollback_request

    try:
        rollback_req = await create_rollback_request(
            db=db,
            original_request_id=request_id,
            requested_by_user_id=current_user.id,
        )
        await db.commit()
        return {
            "rollback_request_id": rollback_req.id,
            "original_request_id": request_id,
            "status": rollback_req.status,
            "entries_queued": rollback_req.processed_rows,
            "entries_skipped": rollback_req.skipped_rows,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
