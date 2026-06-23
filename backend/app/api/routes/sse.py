import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.api.deps.auth import get_current_user

router = APIRouter(prefix="/sse", tags=["sse"])


@router.get("/{request_id}")
async def progress_stream(request_id: str, _=Depends(get_current_user)):
    """
    Server-Sent Events stream for a specific request.
    Frontend connects here and receives progress updates until 'done'.
    """
    async def event_generator():
        from redis.asyncio import Redis  # redis>=4.2 ships redis.asyncio
        r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        channel = f"job_progress:{request_id}"
        try:
            async with r.pubsub() as pubsub:
                await pubsub.subscribe(channel)
                # Send heartbeat
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
            "X-Accel-Buffering": "no",   # nginx: disable buffering for SSE
        },
    )
