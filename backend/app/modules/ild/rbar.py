import logging
from app.models.enums import DecisionType

logger = logging.getLogger(__name__)


async def evaluate_rbar_instance(
    ctx,
    start: int,
    end: int,
    action: str | None = None,
) -> dict:

    # ──────────────────────────────────────────────────────────────
    # Input validation
    # ──────────────────────────────────────────────────────────────
    if action not in {"ADD", "DELETE"}:
        return {
            "decision": DecisionType.SKIPPED.value,
            "reason": f"Invalid action: {action}",
        }

    if start > end:
        return {
            "decision": DecisionType.SKIPPED.value,
            "reason": f"Invalid range: {start}-{end}",
        }

    search_end = end + 1

    # ──────────────────────────────────────────────────────────────
    # 1. Pending Funnel Validation
    # ──────────────────────────────────────────────────────────────
    overlapping_pending = ctx.rbar_pending_tree.overlap(start, search_end)

    dependency_add_relationships = []
    dependency_delete_relationships = []
    supersede_pending_relationships = []

    for p_interval in overlapping_pending:
        p_start = p_interval.begin
        p_end = p_interval.end - 1
        p_action = p_interval.data["action"]
        dep_req = p_interval.data["request_id"]

        # Determine exact relationship bounds
        if start == p_start and end == p_end:
            p_overlap = "exact"
        elif start >= p_start and end <= p_end:
            p_overlap = "sub"
        elif start <= p_start and end >= p_end:
            p_overlap = "super"
        else:
            p_overlap = "partial"

        # Partial overlaps always fall back to mandatory operator review
        if p_overlap == "partial":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": f"Partial overlap with pending request {dep_req}. Review range.",
            }
        
        # Pending ADD vs New ADD
        if p_action == "ADD" and action == "ADD":
            if p_overlap == "exact":
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": f"Duplicate pending ADD request {dep_req}",
                }
            if p_overlap == "sub":
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": f"Sub-range of pending ADD request {dep_req}",
                }
            if p_overlap == "super":
                supersede_pending_relationships.append({
                    "request_id": dep_req,
                    "type": DecisionType.SUPERSEDE_PENDING.value,
                    "relationship": p_overlap,
                })
                continue
        
        # Pending ADD vs New DELETE
        if p_action == "ADD" and action == "DELETE":
            if p_overlap == "exact":
                dependency_delete_relationships.append({
                    "request_id": dep_req,
                    "type": DecisionType.DEPENDENCY_DELETE.value,
                    "relationship": p_overlap,
                })
                continue
            if p_overlap in ("sub", "super"):
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": f"DELETE request does not match pending ADD request {dep_req}",
                }
        
        # Pending DELETE vs New ADD
        if p_action == "DELETE" and action == "ADD":
            dependency_add_relationships.append({
                "request_id": dep_req,
                "type": DecisionType.DEPENDENCY_ADD.value,
                "relationship": p_overlap,
            })
            continue
        
        # Pending DELETE vs New DELETE
        if p_action == "DELETE" and action == "DELETE":
            if p_overlap in ("exact", "sub"):
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": f"Duplicate pending DELETE request {dep_req}",
                }
            if p_overlap == "super":
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": f"DELETE range contains pending DELETE request {dep_req}. Review range.",
                }

    # ──────────────────────────────────────────────────────────────
    # RESOLVE RELATIONSHIPS (Corrected Error Check Hierarchy)
    # ──────────────────────────────────────────────────────────────
    # Critical dependency errors MUST block standard pipeline optimization decisions

    if dependency_delete_relationships:
        logger.info("RBAR DEPENDENCY_DELETE – %s-%s links to pending requests", start, end)
        return {
            "decision": DecisionType.DEPENDENCY_DELETE.value,
            "dependency_note": "Dependent on pending ADD requests",  # Refined for specificity
            "relationships": dependency_delete_relationships,
        }

    # If a new ADD targets an in-flight DELETE request
    if dependency_add_relationships:
        logger.info("RBAR DEPENDENCY_ADD – %s-%s links to pending requests", start, end)
        return {
            "decision": DecisionType.DEPENDENCY_ADD.value,
            "dependency_note": "Dependent on pending DELETE requests", # Refined for specificity
            "relationships": dependency_add_relationships,
        }

    if supersede_pending_relationships:
        logger.info("RBAR SUPERSEDE_PENDING – new %s-%s sweeps pending records", start, end)
        return {
            "decision": DecisionType.SUPERSEDE_PENDING.value,
            "relationships": supersede_pending_relationships,
        }

    # ──────────────────────────────────────────────────────────────
    # 2. Effective Active State Validation
    # ──────────────────────────────────────────────────────────────
    if action == "DELETE":
        exact_match = ctx.rbar_ranges.overlap(start, search_end)
        for interval in exact_match:
            if interval.begin == start and interval.end == search_end:
                return {"decision": DecisionType.DELETE.value}

        logger.warning("RBAR SKIP – range not found for active DELETE: %s-%s", start, end)
        return {
            "decision": DecisionType.SKIPPED.value,
            "reason": "Range not found",
        }

    # ADD Action Overlap Checks
    overlapping_intervals = ctx.rbar_ranges.overlap(start, search_end)
    if not overlapping_intervals:
        return {"decision": DecisionType.ADD.value}

    superseded_ranges = []
    for interval in overlapping_intervals:
        old_start = interval.begin
        old_end = interval.end - 1

        if start == old_start and end == old_end:
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Exact range exists",
            }

        if start >= old_start and end <= old_end:
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": f"Sub-range of existing entry {old_start}-{old_end}",
            }

        if start <= old_start and end >= old_end:
            superseded_ranges.append((old_start, old_end))
            continue

        return {
            "decision": DecisionType.SKIPPED.value,
            "reason": f"Partial overlap with active config {old_start}-{old_end}",
        }

    if superseded_ranges:
        logger.info("RBAR SUPERSEDE – %s-%s replaces active records %s", start, end, superseded_ranges)
        return {
            "decision": DecisionType.SUPERSEDE.value,
            "replace": superseded_ranges,
        }

    return {"decision": DecisionType.ADD.value}