from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db
from app.api.deps.auth import require_operator

router = APIRouter(prefix="/requests", tags=["rollback"])


@router.post("/{request_id}/rollback")
async def rollback_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_operator),
):
    """
    Cancel/rollback a request that has not been fully implemented yet:
    all PENDING / AWAITING_IMPLEMENTATION entries are cancelled and their
    dependency relationships purged.
    """
    from app.modules.ild.rollback import rollback_pending_request

    try:
        original = await rollback_pending_request(
            db=db,
            original_request_id=request_id,
            requested_by_user_id=current_user.id,
        )
        return {
            "original_request_id": request_id,
            "status": original.status,
            "message": "Request cancelled; pending entries purged from the queue.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
