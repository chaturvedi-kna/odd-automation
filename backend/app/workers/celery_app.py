import logging
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

logger = logging.getLogger(__name__)

# Core Static Operational Target Constants
TARGET_TIMEZONE = "Asia/Kolkata"
DEFAULT_QUEUE = "default"


def _cron_from_str(time_str: str) -> crontab:
    """
    Resilient time parser.
    Parses 'HH:MM' strings and enforces strict, user-friendly boundaries.
    """
    if not time_str:
        raise ValueError("Target time string parameter cannot be empty.")
        
    try:
        parts = [p.strip() for p in time_str.strip().split(":") if p.strip()]
        
        # Issue 5 Fix: Enforce exactly two parts to reject malformed data (like HH:MM:SS)
        if len(parts) != 2:
            raise ValueError("Time string must be formatted exactly as HH:MM")
            
        hh = int(parts[0])
        mm = int(parts[1])
        
        # Issue 7 Fix: Clean, standard, operator-friendly boundary alerts
        if not (0 <= hh <= 23):
            raise ValueError(f"Hour must be between 0 and 23. Received: {hh}")
        if not (0 <= mm <= 59):
            raise ValueError(f"Minute must be between 0 and 59. Received: {mm}")
            
        logger.info("Loaded schedule cron slot mapping: %02d:%02d", hh, mm)
        return crontab(hour=hh, minute=mm)
        
    except Exception as ex:
        logger.error(
            "Failed to parse cron string profile context '%s'. "
            "Reverting to fallback default (01:05). Reason: %s", 
            time_str, ex
        )
        return crontab(hour=1, minute=5)


celery_app = Celery(
    "odd_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Hardened production configuration parameters
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone settings configuration mapping boundaries
    timezone=TARGET_TIMEZONE,
    enable_utc=False,
    
    task_track_started=True,
    
    # Performance tuning parameters
    task_acks_late=True,                 # Guarantees heavy dump tasks retry if a worker node crashes
    worker_prefetch_multiplier=1,        # Prevents one worker node from hogging multiple heavy CSV imports
    
    # Prevents worker crashes if Redis is still booting up during a cold start
    broker_connection_retry_on_startup=True,
    
    # Issue 6 Fix: Swapped to a highly scannable explicit time math block
    result_expires=60 * 60 * 24,         # Automatically evicts old task tracking metadata after 24 hours
    
    # Issue 4 Fix: Expose timeout boundaries directly to environment settings attributes
    task_soft_time_limit=int(getattr(settings, "CELERY_SOFT_TIME_LIMIT", 1800)),  # Soft warning timeout (30 mins default)
    task_time_limit=int(getattr(settings, "CELERY_TIME_LIMIT", 2100)),            # Hard thread termination (35 mins default)
    
    # Advanced Task Routing Matrix
    task_default_queue=DEFAULT_QUEUE,
    task_routes={
        "app.workers.tasks.task_process_request": {"queue": "processing"},
        "app.workers.tasks.task_ingest_dump": {"queue": "processing"},
        "app.workers.tasks.task_scan_incoming_dumps": {"queue": "processing"},
        "app.workers.tasks.task_run_reconciliation": {"queue": "scheduler"},
        "app.workers.tasks.task_export_excel": {"queue": "export"},
        "app.workers.tasks.task_dispatch_notifications": {"queue": "notifications"},
    }
)

# ── Issue 1 Fix: Moved timezone verification downstream AFTER conf.update runs ──
if celery_app.conf.timezone != TARGET_TIMEZONE:
    raise RuntimeError(
        f"Critical Timezone Misalignment: expected '{TARGET_TIMEZONE}', "
        f"loaded '{celery_app.conf.timezone}'."
    )
logger.info("Celery engine successfully synchronized with timezone: %s", celery_app.conf.timezone)


# ── Configuration-driven beat schedule ────────────────────────────────────────
# RECON_CRON_TIME   : single HH:MM slot for nightly reconciliation
# DUMP_INGEST_TIMES : comma-separated HH:MM slots for scanning the dump source
BEAT_SCHEDULE = {
    "nightly-reconciliation": {
        "task": "app.workers.tasks.task_run_reconciliation",
        "schedule": _cron_from_str(settings.RECON_CRON_TIME),
    },
}

for _idx, _slot in enumerate(
    (t.strip() for t in settings.DUMP_INGEST_TIMES.split(",") if t.strip()), start=1
):
    BEAT_SCHEDULE[f"dump-ingest-slot-{_idx}"] = {
        "task": "app.workers.tasks.task_scan_incoming_dumps",
        "schedule": _cron_from_str(_slot),
    }

celery_app.conf.beat_schedule = BEAT_SCHEDULE