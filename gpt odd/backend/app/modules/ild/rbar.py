from app.models.enums import DecisionType


def check_overlap(new_start, new_end, old_start, old_end):

    if new_start == old_start and new_end == old_end:
        return "exact"

    if new_start >= old_start and new_end <= old_end:
        return "sub"

    if new_start <= old_start and new_end >= old_end:
        return "super"

    if not (
        new_end < old_start
        or new_start > old_end
    ):
        return "partial"

    return "none"


async def evaluate_rbar_instance(
    ctx,
    start,
    end,
    action="ADD",
):
    pending_info = ctx.pending_range_map.get(
        (start, end)
    )

    # =====================================================
    # DEPENDENCY / DUPLICATE
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
                "decision": (
                    DecisionType.DEPENDENCY_DELETE.value
                ),

                "dependency_note": (
                    f"Pending ADD exists in request "
                    f"{pending_info['request_id']}"
                ),

                "dependency_request_id": pending_info[
                    "request_id"
                ],
            }

        if prev_action == "DELETE" and action == "ADD":
            return {
                "decision": (
                    DecisionType.DEPENDENCY_ADD.value
                ),

                "dependency_note": (
                    f"Pending DELETE exists in request "
                    f"{pending_info['request_id']}"
                ),

                "dependency_request_id": pending_info[
                    "request_id"
                ],
            }

    # =====================================================
    # DELETE
    # =====================================================

    if action == "DELETE":

        for s, e in ctx.rbar_ranges:

            if start == s and end == e:
                return {
                    "decision": DecisionType.DELETE.value
                }

        return {
            "decision": DecisionType.SKIPPED.value,
            "reason": "Range not found",
        }

    # =====================================================
    # ADD LOGIC
    # =====================================================

    for s, e in ctx.rbar_ranges:

        overlap = check_overlap(
            start,
            end,
            s,
            e,
        )

        if overlap == "exact":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Exact range exists",
            }

        if overlap == "sub":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Sub-range exists",
            }

        if overlap == "partial":
            return {
                "decision": DecisionType.SKIPPED.value,
                "reason": "Partial overlap",
            }

        if overlap == "super":
            return {
                "decision": DecisionType.SUPERSEDE.value,
                "replace": (s, e),
            }

    return {
        "decision": DecisionType.ADD.value
    }