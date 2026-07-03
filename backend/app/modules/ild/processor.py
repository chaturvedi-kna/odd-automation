import logging
from datetime import datetime, timezone
import pandas as pd
from intervaltree import Interval

from app.models.enums import DecisionType, ImplStatus, RequestStatus
from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.audit_log import AuditLog
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.entry_instance_relationship import EntryInstanceRelationship

from app.modules.ild.context import InstanceContext
from app.modules.ild.prr import evaluate_prr_instance
from app.modules.ild.rbar import evaluate_rbar_instance
from app.modules.ild.helpers import parse_range
from app.modules.ild.inheritance import inherit_prr_template, inherit_rbar_template
from app.modules.ild.sse import publish_event
from app.core.config import settings

logger = logging.getLogger(__name__)

# Updated to include SUPERSEDE_PENDING per architecture requirements
ACTIONABLE_DECISIONS = {
    DecisionType.ADD.value,
    DecisionType.DELETE.value,
    DecisionType.SUPERSEDE.value,
    DecisionType.SUPERSEDE_PENDING.value,
    DecisionType.DEPENDENCY_ADD.value,
    DecisionType.DEPENDENCY_DELETE.value,
}

ADD_DECISIONS = {DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value}
DELETE_DECISIONS = {DecisionType.DELETE.value, DecisionType.DEPENDENCY_DELETE.value, DecisionType.SUPERSEDE_PENDING.value}


def _ist_now() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Kolkata"))


# Shared config-driven scope filter (PRR = name CONTAINS suffix)
from app.modules.ild.helpers import in_prr_scope as _scope_prr


async def _create_status(
    db,
    request_id: str,
    entry_id: str,
    entry_type: str,
    inst: dict,
    eval_result: dict,
) -> EntryInstanceStatus:
    status = EntryInstanceStatus(
        request_id=request_id,
        entry_id=entry_id,
        entry_type=entry_type,
        dra_type=inst["dra_type"],
        instance_label=inst["instance_label"],
        decision=eval_result["decision"],
        reason=eval_result.get("reason"),
        dependency_note=eval_result.get("dependency_note"),
        impl_status=(
            ImplStatus.PENDING.value
            if eval_result["decision"] in ACTIONABLE_DECISIONS
            else None
        ),
    )
    db.add(status)
    await db.flush()

    relationships = eval_result.get("relationships", [])
    seen_relationships = set()

    for rel in relationships:
        # Fixed: Enhanced composite tracking key prevents data loss across match variants
        rel_key = (rel["request_id"], rel["type"], rel.get("relationship"))
        if rel_key in seen_relationships:
            continue
        seen_relationships.add(rel_key)

        db.add(
            EntryInstanceRelationship(
                instance_status_id=status.id,
                related_request_id=rel["request_id"],
                relationship_type=rel["type"],
                relationship_match_type=rel.get("relationship"), 
            )
        )
    
    if relationships:
        await db.flush()

    return status


async def process_ild_request(
    db,
    request,
    csv_path: str,
    selected_instances: list[dict],
):
    df = pd.read_csv(csv_path)
    rows = df.fillna("").to_dict(orient="records")

    request.status = RequestStatus.PROCESSING.value
    request.total_rows = len(rows)
    await db.flush()

    processed = skipped = failed = 0

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
            def _to_int(v):
                """mcc/mnc are Integer columns; CSV may deliver str/float/NaN."""
                try:
                    return int(float(v)) if str(v).strip() not in ("", "nan", "None") else None
                except (ValueError, TypeError, OverflowError):
                    return None

            prr_entry = PrrEntry(
                request_id=request.id,
                country=row.get("Country") or None,
                operator=row.get("Operator") or None,
                mcc=_to_int(row.get("MCC")),
                mnc=_to_int(row.get("MNC")),
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
                if _scope_prr(rule_raw):
                    prr_eval = await evaluate_prr_instance(ctx, row, request.id)
                    prr_status = await _create_status(db, request.id, prr_entry.id, "PRR", inst, prr_eval)

                    if prr_eval["decision"] in ACTIONABLE_DECISIONS:
                        row_skipped = False

                        inherited = await inherit_prr_template(
                            db, inst["dra_type"], inst["instance_label"], override=row
                        )
                        
                        final_rule_name = prr_eval.get("final_rule") or rule_raw
                        payload = {
                            **inherited,
                            "realm": realm_raw,
                            "final_prt_rule": final_rule_name,
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

                        # Map out standardized action labels for context hydration
                        mapped_action = action  # already normalized upper-case, defaults to ADD

                        # Update live context maps for future batch iterations
                        rl = realm_raw.lower()
                        if rl not in ctx.prr_pending_realms:
                            ctx.prr_pending_realms[rl] = []
                        
                        ctx.prr_pending_realms[rl].append({
                            "action": mapped_action,
                            "request_id": request.id,
                            "rule": final_rule_name.lower()
                        })

                        if prr_eval["decision"] in ADD_DECISIONS:
                            ctx.prr_realms.add(rl)
                            ctx.prr_rules.add(final_rule_name.lower())
                        elif prr_eval["decision"] in DELETE_DECISIONS:
                            ctx.prr_realms.discard(rl)
                # Out-of-scope PRR rows are passed through silently
                # (no log entry, no DB record) per scope-filtering spec.

                # ── RBAR evaluation ───────────────────────────────────────
                if rbar_entry and start_addr is not None:
                    rbar_eval = await evaluate_rbar_instance(ctx, start_addr, end_addr, action)
                    rbar_status = await _create_status(db, request.id, rbar_entry.id, "RBAR", inst, rbar_eval)

                    if rbar_eval["decision"] in ACTIONABLE_DECISIONS:
                        row_skipped = False

                        inherited = await inherit_rbar_template(
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

                        start_i = int(start_addr)
                        end_i = int(end_addr) + 1  
                        
                        mapped_action = action  # already normalized upper-case, defaults to ADD
                        
                        # Sync the RBAR pipeline tree structure
                        ctx.rbar_pending_tree.add(Interval(
                            start_i, end_i, {"action": mapped_action, "request_id": request.id}
                        ))

                        if rbar_eval["decision"] in ADD_DECISIONS:
                            ctx.rbar_ranges.add(Interval(start_i, end_i))
                            
                        elif rbar_eval["decision"] in DELETE_DECISIONS:
                            for iv in list(ctx.rbar_ranges.overlap(start_i, end_i)):
                                if iv.begin == start_i and iv.end == end_i:
                                    ctx.rbar_ranges.discard(iv)
                                    
                        elif rbar_eval["decision"] == DecisionType.SUPERSEDE.value:
                            # Loop over the list of tuples returned by your updated RBAR module
                            for old_start, old_end in rbar_eval.get("replace", []):
                                old_start_i = int(old_start)
                                old_end_i = int(old_end) + 1
                                
                                for iv in list(ctx.rbar_ranges.overlap(old_start_i, old_end_i)):
                                    if iv.begin == old_start_i and iv.end == old_end_i:
                                        ctx.rbar_ranges.discard(iv)

                                del_status = await _create_status(
                                    db, request.id, rbar_entry.id, "RBAR", inst, {
                                        "decision": DecisionType.DELETE.value,
                                        "reason": "Superseded by larger range",
                                    }
                                )
                                db.add(EntryInstanceDetail(
                                    instance_status_id=del_status.id,
                                    entry_id=rbar_entry.id,
                                    entry_type="RBAR",
                                    dra_type=inst["dra_type"],
                                    instance_label=inst["instance_label"],
                                    start_addr=old_start,
                                    end_addr=old_end,
                                    raw_payload={"start_addr": old_start, "end_addr": old_end, "reason": "Superseded"},
                                ))
                            
                            # Insert the newly updated wide master boundary range
                            ctx.rbar_ranges.add(Interval(start_i, end_i))

            if row_skipped:
                skipped += 1
            else:
                processed += 1

        except Exception as ex:
            failed += 1
            logger.exception("Error processing row %d: %s", row_idx, ex)
            db.add(AuditLog(
                request_id=request.id,
                level="ERROR",
                entry_type="ROW",
                message=f"Row {row_idx} error: {ex}",
            ))

        request.processed_rows = processed
        request.skipped_rows = skipped
        request.failed_rows = failed

        publish_event(request.id, {
            "type": "progress",
            "total": len(rows),
            "processed": processed + skipped + failed,
            "processed_ok": processed,
            "skipped": skipped,
            "failed": failed,
        })

    # Fixed: Uses your actual database Enum layout limits 
    request.status = RequestStatus.FAILED.value if failed > 0 else RequestStatus.COMPLETED.value
    request.completed_at = _ist_now()
    
    await db.flush()
    await db.commit()

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