from celery import Celery
from celery.schedules import crontab
from app.core.config import settings


def _cron_from_str(time_str: str) -> crontab:
    """Convert 'HH:MM' string to a Celery crontab schedule."""
    hh, mm = time_str.strip().split(":")
    return crontab(hour=int(hh), minute=int(mm))


celery_app = Celery(
    "odd_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=False,
    task_track_started=True,
    beat_schedule={
        "reconcile-every-night": {
            "task": "app.workers.tasks.task_run_reconciliation",
            "schedule": _cron_from_str(settings.RECON_CRON_TIME),
        },
    },
)
