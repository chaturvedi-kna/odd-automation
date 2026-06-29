"""
Synchronous Redis pub/sub publisher.

Called from the ILD processor which runs inside a Celery task (sync context).
The async SSE route subscribes to the same channel.
"""
import json
import logging
import threading
from typing import Any, Dict

import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import RedisError, ConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Issue 8 Fix: Extracted static channel configuration mapping constant
CHANNEL_PREFIX = "job_progress"

_redis_pool: redis.ConnectionPool | None = None
# Issue 1 Fix: Injected thread lock synchronization handle
_pool_lock = threading.Lock()


def _get_redis_client() -> redis.Redis:
    """
    Thread-Safe Resilient Connection Manager:
    Uses classic double-checked locking patterns to eliminate multi-worker initialization races.
    """
    global _redis_pool
    
    # Outer check: Avoid performance-heavy locking if pool is already hydrated
    if _redis_pool is None:
        with _pool_lock:
            # Inner check: Protects against simultaneous thread race arrivals
            if _redis_pool is None:
                retry_policy = Retry(
                    ExponentialBackoff(cap=10, base=2), 
                    retries=getattr(settings, "REDIS_RETRY_COUNT", 3)
                )
                
                # Issue 7 Fix: Eliminated hardcoded limits to prioritize settings-driven environments
                _redis_pool = redis.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    max_connections=getattr(settings, "REDIS_MAX_CONNECTIONS", 50),
                    socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT", 5.0)),
                    socket_connect_timeout=float(getattr(settings, "REDIS_CONNECT_TIMEOUT", 5.0)),
                    retry=retry_policy,
                    retry_on_timeout=True,
                    retry_on_error=[ConnectionError]
                )
                
    return redis.Redis(connection_pool=_redis_pool)


def publish_event(request_id: str, payload: Dict[str, Any]) -> None:
    """
    Publish a progress/done event to the job_progress channel for a request.
    """
    if not request_id:
        logger.error("SSE publish aborted: Missing valid request_id string parameter context.")
        return

    # Issue 8 Fix: Assembled channel string from configuration boundaries
    channel = f"{CHANNEL_PREFIX}:{request_id}"
    
    try:
        client = _get_redis_client()
        
        # Issue 4 Fix: Enforce default string fallbacks to handle dates, enums, and UUID payloads safely
        serialized_payload = json.dumps(payload, default=str)
        
        # Issue 3 Fix: Track listener tracking counts for metric observability
        subscriber_count = client.publish(channel, serialized_payload)
        
        if subscriber_count == 0:
            logger.debug("No active UI client subscribers currently listening on SSE channel: %s", channel)
            
    except RedisError as exc:
        logger.error(
            "SSE Redis transport failure for request %s on channel %s: %s", 
            request_id, channel, exc, exc_info=True
        )
    except Exception as exc:
        logger.error(
            "Unexpected synchronization anomaly while publishing SSE event for request %s: %s", 
            request_id, exc, exc_info=True
        )