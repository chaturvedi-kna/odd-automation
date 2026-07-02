import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from sqlalchemy import select
from redis.asyncio import Redis

from app.core.config import settings
from app.core.jwt import ALGORITHM
from app.db.deps import get_db
from app.models.user import User

router = APIRouter(prefix="/sse", tags=["sse"])

async def get_sse_user(
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Special dependency for SSE stream to read tokens from query string."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc
    return user

@router.get("/{request_id}")
async def progress_stream(
    request_id: str, 
    _=Depends(get_sse_user)  # Swapped to token-query query string parameter decoder
):
    """
    Server-Sent Events stream for a specific request.
    Frontend connects here and receives progress updates until 'done'.
    """
    async def event_generator():
        r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        channel = f"job_progress:{request_id}"
        try:
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(channel)
                yield "data: {\"type\":\"connected\"}\n\n"
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = message["data"]
                        yield f"data: {data}\n\n"
                        try:
                            payload = json.loads(data)
                            if payload.get("type") == "done":
                                break
                        except Exception:
                            pass
        except asyncio.CancelledError:
            pass
        finally:
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no", 
        },
    )