import json
import redis
from app.core.config import settings

r = redis.from_url(settings.REDIS_URL)


def publish_event(request_id, payload):
    channel = f"job_progress:{request_id}"
    r.publish(channel, json.dumps(payload))