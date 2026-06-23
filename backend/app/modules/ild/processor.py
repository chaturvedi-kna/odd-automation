"""
ILD request processor.
Runs inside a Celery task (via asyncio.run) or directly in tests.
All DB interaction is async.
"""
import logging
from datetime import datetime, timezone

import pandas as pd

from app.models.enums import DecisionType, ImplStatus, RequestStatus
from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.audit_log import AuditLog
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail

from app.modules.ild.context import InstanceContext
from app.modules.ild.prr import evaluate_prr_instance
from app.modules.ild.rbar import evaluate_rbar_instance
from app.modules.ild.helpers import parse_range
from app.modules.ild.inheritance import inherit_prr_config, inherit_rbar_config
from app.modules.ild.sse import publish_event
from app.core.config import settings

logger = logging.getLogger(__name__)

ACTIONABLE_DECISIONS = {
    DecisionType.ADD.value,
    DecisionType.DELETE.value,
    DecisionType.SUPERSEDE.value,
    DecisionType.DEPENDENCY_ADD.value,
    DecisionType.DEPENDENCY_DELETE.value,
}

ADD_DECISIONS = {DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value}
DELETE_DECISIONS = {DecisionType.DELETE.value, DecisionType.DEPENDENCY_DELETE.value}

IST = timezone(datetime.now(timezone.utc).utcoffset())  # approx; use pytz in production


def _ist_now() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def _scope_prr(rule: str) -> bool:
    """Return True if rule name contains any configured PRR scope suffix."""
    suffixes = [s.strip().lower() for s in settings.PRR_SCOPE_SUFFIXES.split(",") if s.strip()]
    rl = rule.lower()
    return any(rl.endswith(suf) or f"_{suf}" in rl for suf in suffixes)


def _scope_rbar(destination: str) -> bool:
    """Return True if destination ends with any configured RBAR scope suffix."""
    suffixes = [s.strip().lower() for s in settings.RBAR_SCOPE_SUFFIXES.split(",") if s.strip()]
    dl = (destination or "").lower()
    return any(dl.endswith(suf) for suf in suffixes)


async def _create_status(
    db,
    entry_id: str,
    entry_type: str,
    inst: dict,
    eval_result: dict,
) -> EntryInstanceStatus:
    status = EntryInstanceStatus(
        entry_id=entry_id,
        entry_type=entry_type,
        dra_type=inst["dra_type"],
        instance_label=inst["instance_label"],
        decision=eval_result["decision"],
        reason=eval_result.get("reason"),
        dependency_note=eval_result.get("dependency_note"),
        dependency_request_id=eval_result.get("dependency_request_id"),
        impl_status=(
            ImplStatus.PENDING.value
            if eval_result["decision"] in ACTIONABLE_DECISIONS
            else None  # FIX: SKIPPED entries should have NULL impl_status
        ),
    )
    db.add(status)
    await db.flush()
    return status


async def process_ild_request(
    db,
    request,
    csv_path: str,
    selected_instances: list[dict],
):
    """
    Main ILD processing loop.
    ``selected_instances`` is a list of dicts: [{dra_type, instance_label}, …]
    """
    df = pd.read_csv(csv_path)
    rows = df.fillna("").to_dict(orient="records")

    # FIX: was "IN_PROGRESS" which is not a valid status enum value
    request.status = RequestStatus.PROCESSING.value
    request.total_rows = len(rows)
    await db.flush()

    processed = skipped = failed = 0

    # Pre-load contexts for all selected instances
    contexts: dict[str, InstanceContext] = {}
    for inst in selected_instances:
        key = f"{inst['dra_type']}|{inst['instance_label']}"
        contexts[key] = await InstanceContext.load(db, inst["dra_type"], inst["instance_label"])

    for row_idx, row in enumerate(rows):
        try:
            rule_raw = (row.get("PRT Rule") or "").strip()
            realm_raw = (row.get("Realm") or "").strip()
            range_raw = (row.get("Range") or "").strip()
            action = (row.get("ACTION") or "ADD").upper()

            # ── Create PRR entry ─────────────────────────────────────────
            prr_entry = PrrEntry(
                request_id=request.id,
                country=row.get("Country") or None,
                operator=row.get("Operator") or None,
                mcc=row.get("MCC") or None,
                mnc=row.get("MNC") or None,
                realm=realm_raw,
                prt_rule=rule_raw,
                action=action,
                raw_payload=row,
            )
            db.add(prr_entry)
            await db.flush()

            # ── Optionally create RBAR entry ─────────────────────────────
            rbar_entry = None
            start_addr = end_addr = None

            if range_raw and range_raw not in ("", "-"):
                start_addr, end_addr = parse_range(range_raw)
                rbar_entry = RbarEntry(
                    request_id=request.id,
                    realm=realm_raw,
                    start_addr=start_addr,
                    end_addr=end_addr,
                    action=action,
                    raw_payload=row,
                )
                db.add(rbar_entry)
                await db.flush()

            row_skipped = True

            for inst in selected_instances:
                key = f"{inst['dra_type']}|{inst['instance_label']}"
                ctx = contexts[key]

                # ── PRR evaluation ────────────────────────────────────────
                # Scope filter: only manage rows where rule matches PRR scope
                if _scope_prr(rule_raw):
                    prr_eval = await evaluate_prr_instance(ctx, row, request.id)
                    prr_status = await _create_status(db, prr_entry.id, "PRR", inst, prr_eval)

                    if prr_eval["decision"] in ACTIONABLE_DECISIONS:
                        row_skipped = False

                        # FIX: was passing `realm` positional arg that doesn't exist
                        inherited = await inherit_prr_config(
                            db, inst["dra_type"], inst["instance_label"], override=row
                        )
                        payload = {
                            **inherited,
                            "realm": realm_raw,
                            "final_prt_rule": prr_eval.get("final_rule") or rule_raw,
                        }

                        detail = EntryInstanceDetail(
                            instance_status_id=prr_status.id,
                            entry_id=prr_entry.id,
                            entry_type="PRR",
                            dra_type=inst["dra_type"],
                            instance_label=inst["instance_label"],
                            final_prt_rule=payload["final_prt_rule"],
                            realm=payload["realm"],
                            raw_payload=payload,
                        )
                        db.add(detail)

                        # Update live context
                        rl = realm_raw.lower()
                        if prr_eval["decision"] in ADD_DECISIONS:
                            ctx.prr_realms.add(rl)
                            ctx.prr_rules.add(payload["final_prt_rule"].lower())
                        elif prr_eval["decision"] in DELETE_DECISIONS:
                            ctx.prr_realms.discard(rl)
                else:
                    db.add(AuditLog(
                        request_id=request.id,
                        level="DEBUG",
                        entry_type="PRR",
                        message=f"Out-of-scope PRR row skipped: rule={rule_raw}",
                        instance_label=inst["instance_label"],
                        dra_type=inst["dra_type"],
                    ))

                # ── RBAR evaluation ───────────────────────────────────────
                if rbar_entry and start_addr is not None:
                    # Scope filter: destination from row (not yet in dump, use RBAR_SCOPE_SUFFIXES)
                    # For input CSV we treat all RBAR entries as in-scope (destination comes from dump)
                    rbar_eval = await evaluate_rbar_instance(ctx, start_addr, end_addr, action)
                    rbar_status = await _create_status(db, rbar_entry.id, "RBAR", inst, rbar_eval)

                    if rbar_eval["decision"] in ACTIONABLE_DECISIONS:
                        row_skipped = False

                        # FIX: was passing start/end positional args that don't exist in signature
                        inherited = await inherit_rbar_config(
                            db, inst["dra_type"], inst["instance_label"], override=row
                        )
                        payload = {
                            **inherited,
                            "start_addr": start_addr,
                            "end_addr": end_addr,
                        }

                        detail = EntryInstanceDetail(
                            instance_status_id=rbar_status.id,
                            entry_id=rbar_entry.id,
                            entry_type="RBAR",
                            dra_type=inst["dra_type"],
                            instance_label=inst["instance_label"],
                            start_addr=start_addr,
                            end_addr=end_addr,
                            destination=payload.get("destination"),
                            raw_payload=payload,
                        )
                        db.add(detail)

                        # Update live context
                        rk = (start_addr, end_addr)
                        if rbar_eval["decision"] in ADD_DECISIONS:
                            if rk not in ctx.rbar_ranges:
                                ctx.rbar_ranges.append(rk)
                        elif rbar_eval["decision"] in DELETE_DECISIONS:
                            ctx.rbar_ranges = [r for r in ctx.rbar_ranges if r != rk]
                        elif rbar_eval["decision"] == DecisionType.SUPERSEDE.value:
                            old = rbar_eval["replace"]
                            ctx.rbar_ranges = [r for r in ctx.rbar_ranges if r != old]
                            ctx.rbar_ranges.append(rk)

                            # Create a companion DELETE status for the superseded range
                            del_eval = {
                                "decision": DecisionType.DELETE.value,
                                "reason": "Superseded by larger range",
                            }
                            del_status = await _create_status(
                                db, rbar_entry.id, "RBAR", inst, del_eval
                            )
                            db.add(EntryInstanceDetail(
                                instance_status_id=del_status.id,
                                entry_id=rbar_entry.id,
                                entry_type="RBAR",
                                dra_type=inst["dra_type"],
                                instance_label=inst["instance_label"],
                                start_addr=old[0],
                                end_addr=old[1],
                                raw_payload={"start_addr": old[0], "end_addr": old[1],
                                             "reason": "Superseded"},
                            ))

            if row_skipped:
                skipped += 1
            else:
                processed += 1

        except Exception as ex:   # FIX: was `except Exception:` but then referenced undefined `ex`
            failed += 1
            logger.exception("Error processing row %d: %s", row_idx, ex)
            db.add(AuditLog(
                request_id=request.id,
                level="ERROR",
                entry_type="ROW",
                # FIX: AuditLog has no raw_payload column
                message=f"Row {row_idx} error: {ex}",
            ))

        # FIX: moved counter updates INSIDE the loop (was outside, only updated once)
        request.processed_rows = processed
        request.skipped_rows = skipped
        request.failed_rows = failed

        # Publish SSE progress
        publish_event(request.id, {
            "type": "progress",
            "total": len(rows),
            "processed": processed + skipped + failed,
            "processed_ok": processed,
            "skipped": skipped,
            "failed": failed,
        })

    # FIX: was "COMPLETED" – not a valid RequestStatus value
    request.status = (
        RequestStatus.DONE_PARTIAL.value if failed else RequestStatus.DONE.value
    )
    request.completed_at = _ist_now()

    publish_event(request.id, {
        "type": "done",
        "status": request.status,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    })

    return {
        "status": request.status,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    }
