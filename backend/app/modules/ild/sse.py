"""
Synchronous Redis pub/sub publisher.

Called from the ILD processor which runs inside a Celery task (sync context).
The async SSE route subscribes to the same channel.
"""
import json
import logging

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def publish_event(request_id: str, payload: dict) -> None:
    """Publish a progress/done event to the job_progress channel for a request."""
    channel = f"job_progress:{request_id}"
    try:
        _get_redis().publish(channel, json.dumps(payload))
    except Exception as exc:
        logger.warning("SSE publish failed for request %s: %s", request_id, exc)
