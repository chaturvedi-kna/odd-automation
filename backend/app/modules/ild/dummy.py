import logging
from app.models.enums import DecisionType
from app.core.config import settings

logger = logging.getLogger(__name__)


def _make_renamed_rule(rule: str, unavailable_rules: set) -> str | None:
    """
    Collision-safe PRR rule rename:
      ild_dte_s6a → ild_dte2_s6a → ild_dte3_s6a …
    """
    max_len = settings.PRR_NAME_MAX_LEN

    if "_" in rule:
        parts = rule.rsplit("_", 1)
        prefix = parts[0]
        suffix = parts[1]
    else:
        prefix = rule
        suffix = ""

    i = 2
    while True:
        if suffix:
            candidate = f"{prefix}{i}_{suffix}"
        else:
            candidate = f"{prefix}{i}"

        if len(candidate) > max_len:
            return None

        if candidate.lower() not in unavailable_rules:
            return candidate
        i += 1


async def evaluate_prr_instance(ctx, row: dict, request_id: str) -> dict:
    realm = (row.get("Realm") or "").strip().lower()
    rule = (row.get("PRT Rule") or "").strip().lower()
    action = (row.get("ACTION") or "ADD").upper()

    if action not in {"ADD", "DELETE"}:
        return {"decision": DecisionType.SKIPPED.value, "reason": f"Invalid action: {action}"}

    if not realm:
        return {"decision": DecisionType.SKIPPED.value, "reason": "Missing mandatory Realm parameter"}
    
    if action == "ADD" and not rule:
        return {"decision": DecisionType.SKIPPED.value, "reason": "Missing mandatory PRT Rule parameter",}

    dependency_add_relationships = []
    dependency_delete_relationships = []

    # Combine active running snapshot rules + pending rules into a single look-up constraint
    all_unavailable_rules = ctx.prr_rules

    # ──────────────────────────────────────────────────────────────
    # 1. Pending Funnel Validation (Chained Pipeline Checks)
    # ──────────────────────────────────────────────────────────────
    # FIX FOR ERROR 2: Iterating across a full historical list of modifications
    pending_items = ctx.prr_pending_realms.get(realm, [])
    
    effective_pending_action = None
    
    for item in pending_items:
        effective_pending_action = item["action"]
    
    dependency_add_relationships = []
    dependency_delete_relationships = []
    
    for item in pending_items:
    
        p_action = item["action"]
        dep_req = item["request_id"]
    
        # ------------------------------------------------------
        # Pending ADD vs New DELETE
        # ------------------------------------------------------
        if p_action == "ADD" and action == "DELETE":
    
            dependency_delete_relationships.append(
                {
                    "request_id": dep_req,
                    "type": DecisionType.DEPENDENCY_DELETE.value,
                }
            )
    
        # ------------------------------------------------------
        # Pending DELETE vs New ADD
        # ------------------------------------------------------
        elif p_action == "DELETE" and action == "ADD":
    
            dependency_add_relationships.append(
                {
                    "request_id": dep_req,
                    "type": DecisionType.DEPENDENCY_ADD.value,
                }
            )
    
    # ----------------------------------------------------------
    # Evaluate effective state of pending chain
    # ----------------------------------------------------------
    
    if action == "ADD":
    
        if effective_pending_action == "ADD":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": (
                    f"Duplicate pending ADD request "
                    f"for realm '{realm}'"
                ),
            }
    
        if dependency_add_relationships:
            logger.info(
                "PRR DEPENDENCY_ADD – Realm %s depends on pending requests",
                realm,
            )
    
            final_rule = rule
    
            if rule in all_unavailable_rules:
                final_rule = _make_renamed_rule(
                    rule,
                    all_unavailable_rules,
                )
    
                if final_rule is None:
                    return {
                        "decision": DecisionType.SKIPPED.value,
                        "reason": (
                            f"Name conflict: rename would exceed "
                            f"{settings.PRR_NAME_MAX_LEN} char limit."
                        ),
                    }
    
            return {
                "decision": DecisionType.DEPENDENCY_ADD.value,
                "final_rule": final_rule,
                "relationships": dependency_add_relationships,
            }
    
    if action == "DELETE":
    
        if effective_pending_action == "DELETE":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": (
                    f"Duplicate pending DELETE request "
                    f"for realm '{realm}'"
                ),
            }
    
        if dependency_delete_relationships:
            return {
                "decision": DecisionType.DEPENDENCY_DELETE.value,
                "relationships": dependency_delete_relationships,
            }

    # ──────────────────────────────────────────────────────────────
    # Resolve Pipeline Relationship Dependencies
    # ──────────────────────────────────────────────────────────────
    if dependency_delete_relationships:
        logger.info("PRR DEPENDENCY_DELETE – Realm %s depends on pending requests", realm)
        return {
            "decision": DecisionType.DEPENDENCY_DELETE.value,
            "dependency_note": "Dependent on pending ADD requests",
            "relationships": dependency_delete_relationships,
        }

    if dependency_add_relationships:
        logger.info("PRR DEPENDENCY_ADD – Realm %s depends on pending requests", realm)
        final_rule = rule
        if rule in all_unavailable_rules:
            final_rule = _make_renamed_rule(rule, all_unavailable_rules)
            if final_rule is None:
                logger.error("PRR SKIP – Rename would exceed %d char limit for realm %s", settings.PRR_NAME_MAX_LEN, realm)
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": f"Name conflict: rename would exceed {settings.PRR_NAME_MAX_LEN} char limit.",
                }
        return {
            "decision": DecisionType.DEPENDENCY_ADD.value,
            "final_rule": final_rule,
            "dependency_note": "Dependent on pending DELETE requests",
            "relationships": dependency_add_relationships,
        }

    # ──────────────────────────────────────────────────────────────
    # 2. Static Active State Validation
    # ──────────────────────────────────────────────────────────────
    
    # ADJUSTED EXPECTED BEHAVIOR FOR ERROR 3: Validate and clear exclusively via Realm anchor
    if action == "DELETE":
        if realm not in ctx.prr_realms:
            logger.warning("PRR SKIP – Realm not found for active DELETE: %s", realm)
            return {"decision": DecisionType.SKIPPED.value, "reason": "Realm not found"}
            
        return {"decision": DecisionType.DELETE.value}

    # ADD Action Validation
    if realm in ctx.prr_realms:
        logger.warning("PRR SKIP – Realm already exists in active configs: %s", realm)
        return {"decision": DecisionType.SKIPPED.value, "reason": "Realm already exists"}

    final_rule = rule
    if rule in all_unavailable_rules:
        final_rule = _make_renamed_rule(rule, all_unavailable_rules)
        if final_rule is None:
            logger.error("PRR SKIP – Rename would exceed %d char limit for realm %s", settings.PRR_NAME_MAX_LEN, realm)
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": f"Name conflict: rename would exceed {settings.PRR_NAME_MAX_LEN} char limit.",
            }

    return {"decision": DecisionType.ADD.value, "final_rule": final_rule}