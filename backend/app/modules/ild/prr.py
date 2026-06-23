import logging
from app.models.enums import DecisionType
from app.core.config import settings

logger = logging.getLogger(__name__)


def _make_renamed_rule(rule: str, ctx_prr_rules: set) -> str | None:
    """
    Collision-safe PRR rule rename:
      ild_dte_s6a → ild_dte2_s6a → ild_dte3_s6a …
    Inserts an incrementing digit (starting at 2) directly before the last
    underscore+suffix segment.  Returns None if the shortest candidate would
    already exceed PRR_NAME_MAX_LEN (caller must SKIP + log).
    """
    max_len = settings.PRR_NAME_MAX_LEN

    if "_" in rule:
        parts = rule.rsplit("_", 1)
        prefix = parts[0]   # e.g. "ILD_IRN11"
        suffix = parts[1]   # e.g. "S6a"
    else:
        prefix = rule
        suffix = ""

    i = 2   # FIX: requirement says ild_dte_s6a → ild_dte2_s6a (starts at 2, no zfill)
    while True:
        if suffix:
            candidate = f"{prefix}{i}_{suffix}"
        else:
            candidate = f"{prefix}{i}"

        if len(candidate) > max_len:
            # Even smallest candidate is too long – caller must skip
            return None

        if candidate.lower() not in ctx_prr_rules:
            return candidate
        i += 1


async def evaluate_prr_instance(ctx, row: dict, request_id: str) -> dict:
    realm = (row.get("Realm") or "").strip().lower()
    rule = (row.get("PRT Rule") or "").strip().lower()
    action = (row.get("ACTION") or "ADD").upper()

    # FIX: was ctx.pending_map; now ctx.prr_pending_map with proper dict structure
    pending_info = ctx.prr_pending_map.get(realm)

    # ── DEPENDENCY / DUPLICATE CHECK ──────────────────────────────────────
    if pending_info:
        prev_action = pending_info["action"]    # FIX: was pending_info["action"] on a tuple
        dep_req = pending_info["request_id"]

        if prev_action == "ADD" and action == "ADD":
            logger.warning("PRR SKIP – duplicate pending ADD for realm %s", realm)
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Duplicate pending ADD",
            }

        if prev_action == "DELETE" and action == "DELETE":
            logger.warning("PRR SKIP – duplicate pending DELETE for realm %s", realm)
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Duplicate pending DELETE",
            }

        if prev_action == "ADD" and action == "DELETE":
            logger.warning("PRR DEPENDENCY_DELETE – realm %s has pending ADD in %s", realm, dep_req)
            return {
                "decision": DecisionType.DEPENDENCY_DELETE.value,
                "dependency_note": f"Pending ADD exists in request {dep_req}",
                "dependency_request_id": dep_req,
            }

        if prev_action == "DELETE" and action == "ADD":
            final_rule = rule
            if rule in ctx.prr_rules:
                final_rule = _make_renamed_rule(rule, ctx.prr_rules)
                if final_rule is None:
                    logger.error(
                        "PRR SKIP – Name conflict: rename would exceed %d char limit. "
                        "Manual intervention required. realm=%s rule=%s",
                        settings.PRR_NAME_MAX_LEN, realm, rule,
                    )
                    return {
                        "decision": DecisionType.SKIPPED.value,
                        "reason": (
                            f"Name conflict: rename would exceed {settings.PRR_NAME_MAX_LEN} "
                            "char limit. Manual intervention required."
                        ),
                    }
            return {
                "decision": DecisionType.DEPENDENCY_ADD.value,
                "final_rule": final_rule,
                "dependency_note": f"Pending DELETE exists in request {dep_req}",
                "dependency_request_id": dep_req,
            }

    # ── ADD ───────────────────────────────────────────────────────────────
    if action == "ADD":
        if realm in ctx.prr_realms:
            logger.warning("PRR SKIP – realm already exists: %s", realm)
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Realm already exists",
            }

        final_rule = rule
        if rule in ctx.prr_rules:
            final_rule = _make_renamed_rule(rule, ctx.prr_rules)
            if final_rule is None:
                logger.error(
                    "PRR SKIP – Name conflict: rename would exceed %d char limit. "
                    "Manual intervention required. realm=%s rule=%s",
                    settings.PRR_NAME_MAX_LEN, realm, rule,
                )
                return {
                    "decision": DecisionType.SKIPPED.value,
                    "reason": (
                        f"Name conflict: rename would exceed {settings.PRR_NAME_MAX_LEN} "
                        "char limit. Manual intervention required."
                    ),
                }

        return {"decision": DecisionType.ADD.value, "final_rule": final_rule}

    # ── DELETE ────────────────────────────────────────────────────────────
    if action == "DELETE":
        if realm not in ctx.prr_realms:
            logger.warning("PRR SKIP – realm not found for DELETE: %s", realm)
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Realm not found",
            }
        return {"decision": DecisionType.DELETE.value}

    logger.warning("PRR SKIP – invalid action: %s", action)
    return {"decision": DecisionType.SKIPPED.value, "reason": "Invalid action"}
