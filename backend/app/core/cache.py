"""
Cache refresh strategy using Redis.

Pattern: cache-aside with TTL.
- read:  try cache → on miss, load from DB, store in cache
- write: invalidate relevant cache keys

Key namespaces:
  dashboard:summary          → 60 s TTL
  dashboard:analytics:<days> → 300 s TTL
  instances:tree             → 3600 s TTL (changes rarely)
  instances:list             → 3600 s TTL
"""
import json
import logging
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None

# TTL constants (seconds)
TTL_DASHBOARD_SUMMARY = 60
TTL_DASHBOARD_ANALYTICS = 300
TTL_INSTANCES = 3600


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def cache_get(key: str) -> Any | None:
    try:
        raw = _get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning("cache_get error key=%s: %s", key, e)
        return None


def cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        _get_redis().setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning("cache_set error key=%s: %s", key, e)


def cache_delete(*keys: str) -> None:
    try:
        _get_redis().delete(*keys)
    except Exception as e:
        logger.warning("cache_delete error keys=%s: %s", keys, e)


# ── Targeted invalidation helpers ─────────────────────────────────────────────

def invalidate_dashboard() -> None:
    """Call after any request status change or reconciliation completes."""
    try:
        r = _get_redis()
        keys = r.keys("dashboard:*")
        if keys:
            r.delete(*keys)
    except Exception as e:
        logger.warning("invalidate_dashboard error: %s", e)


def invalidate_instances() -> None:
    """Call after DRA instance records change."""
    cache_delete("instances:tree", "instances:list")
