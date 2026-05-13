from app.models.enums import DecisionType


async def evaluate_prr_instance(
    ctx,
    row,
    request_id,
):
    realm = (row.get("Realm") or "").strip().lower()

    rule = (row.get("PRT Rule") or "").strip().lower()

    action = (row.get("ACTION") or "ADD").upper()

    pending_info = ctx.pending_map.get(realm)

    # =====================================================
    # DEPENDENCY / DUPLICATE CHECK
    # =====================================================

    if pending_info:

        prev_action = pending_info["action"]

        if prev_action == "ADD" and action == "ADD":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Duplicate pending ADD",
            }

        if prev_action == "DELETE" and action == "DELETE":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Duplicate pending DELETE",
            }

        if prev_action == "ADD" and action == "DELETE":
            return {
                "decision": DecisionType.DEPENDENCY_DELETE.value,

                "dependency_note": (
                    f"Pending ADD exists in request "
                    f"{pending_info['request_id']}"
                ),

                "dependency_request_id": pending_info[
                    "request_id"
                ],
            }

        if prev_action == "DELETE" and action == "ADD":

            final_rule = rule

            # If the rule name is already taken, apply the '01', '02' padding logic
            if rule in ctx.prr_rules:
                if "_" in rule:
                    parts = rule.rsplit("_", 1)
                    prefix = parts[0]  # e.g., ILD_IRN11
                    suffix = parts[1]  # e.g., S6a
                else:
                    prefix = rule
                    suffix = ""

                i = 1
                while True:
                    # zfill(2) turns 1 into '01', 2 into '02', etc.
                    counter = str(i).zfill(2)

                    if suffix:
                        candidate = f"{prefix}{counter}_{suffix}"
                    else:
                        candidate = f"{prefix}{counter}"

                    if candidate not in ctx.prr_rules:
                        final_rule = candidate
                        break
                    i += 1

            return {
                "decision": DecisionType.DEPENDENCY_ADD.value,
                "final_rule": final_rule,

                "dependency_note": (
                    f"Pending DELETE exists in request "
                    f"{pending_info['request_id']}"
                ),

                "dependency_request_id": pending_info[
                    "request_id"
                ],
            }

    # =====================================================
    # ADD
    # =====================================================

    if action == "ADD":
        if realm in ctx.prr_realms:
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Realm already exists",
            }

        final_rule = rule

        # If the rule name is already taken, apply the '01', '02' padding logic
        if rule in ctx.prr_rules:
            if "_" in rule:
                parts = rule.rsplit("_", 1)
                prefix = parts[0]  # e.g., ILD_IRN11
                suffix = parts[1]  # e.g., S6a
            else:
                prefix = rule
                suffix = ""

            i = 1
            while True:
                # zfill(2) turns 1 into '01', 2 into '02', etc.
                counter = str(i).zfill(2)
                
                if suffix:
                    candidate = f"{prefix}{counter}_{suffix}"
                else:
                    candidate = f"{prefix}{counter}"

                if candidate not in ctx.prr_rules:
                    final_rule = candidate
                    break
                i += 1

        return {
            "decision": DecisionType.ADD.value,
            "final_rule": final_rule,
        }

    # =====================================================
    # DELETE
    # =====================================================

    if action == "DELETE":

        if realm not in ctx.prr_realms:
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Realm not found",
            }

        return {
            "decision": DecisionType.DELETE.value,
        }

    return {
        "decision": DecisionType.SKIPPED.value,
        "reason": "Invalid action",
    }