"""
Celery tasks.

process_request  – run the ILD processor for a queued ChangeRequest
ingest_dump      – parse and store a dump file
task_run_reconciliation – scheduled reconciliation
"""
import asyncio
import logging
import shutil
from pathlib import Path

from app.workers.celery_app import celery_app
from app.db.session import SyncSessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.process_request", bind=True, max_retries=2)
def process_request(self, request_id: str, csv_path: str, selected_instances: list):
    """Run the async ILD processor inside a sync Celery task."""
    from app.modules.ild.processor import process_ild_request

    async def _run():
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.change_request import ChangeRequest

        async with AsyncSessionLocal() as db:
            req = (await db.execute(
                select(ChangeRequest).where(ChangeRequest.id == request_id)
            )).scalars().first()

            if not req:
                logger.error("process_request: request %s not found", request_id)
                return

            try:
                result = await process_ild_request(db, req, csv_path, selected_instances)
                await db.commit()
                return result
            except Exception as exc:
                await db.rollback()
                logger.exception("process_request failed for %s: %s", request_id, exc)
                from app.models.enums import RequestStatus
                req.status = RequestStatus.FAILED.value
                await db.commit()
                raise self.retry(exc=exc, countdown=30)

    return asyncio.run(_run())


@celery_app.task(name="app.workers.tasks.ingest_dump")
def ingest_dump(
    file_path: str,
    dra_type: str,
    instance_label: str,
    original_filename: str,
):
    """Parse a dump file and store rows in the DB."""
    from app.modules.ild.parser import _detect_type, parse_prr_dump, parse_rbar_dump, _extract_timestamp
    from app.models.dump_snapshot import DumpSnapshot
    from app.models.prr_dump_row import PrrDumpRow
    from app.models.rbar_dump_row import RbarDumpRow

    dump_type = _detect_type(original_filename)
    source_ts = _extract_timestamp(original_filename)

    with SyncSessionLocal() as db:
        snapshot = DumpSnapshot(
            dra_type=dra_type,
            instance_label=instance_label,
            object_type=dump_type,
            file_name=original_filename,
            source_timestamp=source_ts,
        )
        db.add(snapshot)
        db.flush()

        if dump_type == "PRR":
            rows = parse_prr_dump(file_path)
            for r in rows:
                db.add(PrrDumpRow(
                    snapshot_id=snapshot.id,
                    name=r["name"],
                    realm=r["realm"],
                    route_list_name=r["route_list_name"],
                    peer_route_table=r["peer_route_table"],
                    raw_payload=r["raw_payload"],
                ))
        else:
            rows = parse_rbar_dump(file_path)
            for r in rows:
                db.add(RbarDumpRow(
                    snapshot_id=snapshot.id,
                    table_name=r["table_name"],
                    start_addr=r["start_addr"],
                    end_addr=r["end_addr"],
                    destination=r["destination"],
                    raw_payload=r["raw_payload"],
                ))

        db.commit()
        logger.info("Ingested %s dump for %s/%s: %d rows", dump_type, dra_type, instance_label, len(rows))

    # Move to processed
    dest = Path(settings.DUMP_PROCESSED_PATH) / original_filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(file_path, str(dest))

    return {"snapshot_id": snapshot.id, "rows": len(rows)}


@celery_app.task(name="app.workers.tasks.task_run_reconciliation")
def task_run_reconciliation(dra_type: str | None = None, instance_label: str | None = None):
    """Run the reconciliation engine (sync)."""
    from app.modules.ild.reconciler import run_reconciliation

    with SyncSessionLocal() as db:
        result = run_reconciliation(db, dra_type, instance_label)

    logger.info("Reconciliation result: %s", result)
    return result
