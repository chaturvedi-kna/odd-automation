# FINAL VERSION ONLY
# (trimmed comments intentionally)

from datetime import datetime
import pandas as pd

from app.models.enums import (
    DecisionType,
    ImplStatus,
)

from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.audit_log import AuditLog
from app.models.entry_instance_status import (
    EntryInstanceStatus,
)
from app.models.entry_instance_detail import (
    EntryInstanceDetail,
)

from app.modules.ild.context import InstanceContext
from app.modules.ild.prr import evaluate_prr_instance
from app.modules.ild.rbar import evaluate_rbar_instance
from app.modules.ild.helpers import parse_range
from app.modules.ild.inheritance import (
    inherit_prr_config,
    inherit_rbar_config,
)


ACTIONABLE_DECISIONS = [
    DecisionType.ADD.value,
    DecisionType.DELETE.value,
    DecisionType.SUPERSEDE.value,
    DecisionType.DEPENDENCY_ADD.value,
    DecisionType.DEPENDENCY_DELETE.value,
]


async def create_status(
    db,
    entry_id,
    entry_type,
    inst,
    eval_result,
):
    status = EntryInstanceStatus(
        entry_id=entry_id,
        entry_type=entry_type,

        dra_type=inst["dra_type"],
        instance_label=inst["instance_label"],

        decision=eval_result["decision"],

        reason=eval_result.get("reason"),

        dependency_note=eval_result.get(
            "dependency_note"
        ),

        dependency_request_id=eval_result.get(
            "dependency_request_id"
        ),

        impl_status=(
            ImplStatus.PENDING.value
            if eval_result["decision"]
            in ACTIONABLE_DECISIONS
            else None
        ),
    )

    db.add(status)
    await db.flush()

    return status


async def process_ild_request(
    db,
    request,
    csv_path,
    selected_instances,
    settings,
):
    df = pd.read_csv(csv_path)

    rows = df.fillna("").to_dict(
        orient="records"
    )

    request.status = "IN_PROGRESS"

    request.total_rows = len(rows)

    processed = 0
    skipped = 0
    failed = 0

    contexts = {}

    for inst in selected_instances:

        key = (
            f"{inst['dra_type']}|"
            f"{inst['instance_label']}"
        )

        contexts[key] = await InstanceContext.load(
            db,
            inst["dra_type"],
            inst["instance_label"],
        )

    for row in rows:

        try:

            prr_entry = PrrEntry(
                request_id=request.id,

                country=row.get("Country"),
                operator=row.get("Operator"),
                mcc=row.get("MCC"),
                mnc=row.get("MNC"),

                realm=row.get("Realm"),
                prt_rule=row.get("PRT Rule"),

                action=row.get("ACTION", "ADD"),

                raw_payload=row,
            )

            db.add(prr_entry)
            await db.flush()

            rbar_entry = None

            range_value = (
                row.get("Range") or ""
            ).strip()

            start_addr = None
            end_addr = None

            if range_value and range_value != "-":

                start_addr, end_addr = parse_range(
                    range_value
                )

                rbar_entry = RbarEntry(
                    request_id=request.id,

                    realm=row.get("Realm"),

                    start_addr=start_addr,
                    end_addr=end_addr,

                    action=row.get("ACTION", "ADD"),

                    raw_payload=row,
                )

                db.add(rbar_entry)
                await db.flush()

            row_skipped = True

            for inst in selected_instances:

                key = (
                    f"{inst['dra_type']}|"
                    f"{inst['instance_label']}"
                )

                ctx = contexts[key]

                # =====================================
                # PRR
                # =====================================

                prr_eval = await evaluate_prr_instance(
                    ctx,
                    row,
                    request.id,
                )

                prr_status = await create_status(
                    db,
                    prr_entry.id,
                    "PRR",
                    inst,
                    prr_eval,
                )

                if (
                    prr_eval["decision"]
                    in ACTIONABLE_DECISIONS
                ):

                    row_skipped = False

                    inherited = (
                        await inherit_prr_config(
                            db,
                            inst["dra_type"],
                            inst["instance_label"],
                            override=row,
                        )
                    )

                    payload = dict(inherited)

                    payload["realm"] = row.get(
                        "Realm"
                    )

                    payload[
                        "final_prt_rule"
                    ] = prr_eval.get(
                        "final_rule"
                    )

                    detail = EntryInstanceDetail(
                        instance_status_id=prr_status.id,

                        entry_id=prr_entry.id,
                        entry_type="PRR",

                        dra_type=inst["dra_type"],

                        instance_label=inst[
                            "instance_label"
                        ],

                        final_prt_rule=payload.get(
                            "final_prt_rule"
                        ),

                        realm=payload.get("realm"),

                        raw_payload=payload,
                    )

                    db.add(detail)

                    realm_lower = payload[
                        "realm"
                    ].lower()

                    if (
                        prr_eval["decision"]
                        in [
                            DecisionType.ADD.value,
                            DecisionType.DEPENDENCY_ADD.value,
                        ]
                    ):

                        ctx.prr_realms.add(
                            realm_lower
                        )

                        ctx.prr_rules.add(
                            payload[
                                "final_prt_rule"
                            ].lower()
                        )

                    elif (
                        prr_eval["decision"]
                        in [
                            DecisionType.DELETE.value,
                            DecisionType.DEPENDENCY_DELETE.value,
                        ]
                    ):

                        ctx.prr_realms.discard(
                            realm_lower
                        )

                # =====================================
                # RBAR
                # =====================================

                if rbar_entry:

                    rbar_eval = (
                        await evaluate_rbar_instance(
                            ctx,
                            start_addr,
                            end_addr,
                            row.get(
                                "ACTION",
                                "ADD",
                            ),
                        )
                    )

                    rbar_status = await create_status(
                        db,
                        rbar_entry.id,
                        "RBAR",
                        inst,
                        rbar_eval,
                    )

                    if (
                        rbar_eval["decision"]
                        in ACTIONABLE_DECISIONS
                    ):

                        row_skipped = False

                        inherited = (
                            await inherit_rbar_config(
                                db,
                                inst["dra_type"],
                                inst["instance_label"],
                                override=row,
                            )
                        )

                        payload = dict(inherited)

                        payload[
                            "start_addr"
                        ] = start_addr

                        payload[
                            "end_addr"
                        ] = end_addr

                        detail = (
                            EntryInstanceDetail(
                                instance_status_id=(
                                    rbar_status.id
                                ),

                                entry_id=(
                                    rbar_entry.id
                                ),

                                entry_type="RBAR",

                                dra_type=inst[
                                    "dra_type"
                                ],

                                instance_label=inst[
                                    "instance_label"
                                ],

                                start_addr=(
                                    start_addr
                                ),

                                end_addr=end_addr,

                                destination=(
                                    payload.get(
                                        "destination"
                                    )
                                ),

                                raw_payload=payload,
                            )
                        )

                        db.add(detail)

                        # =============================
                        # CONTEXT UPDATE
                        # =============================

                        if (
                            rbar_eval["decision"]
                            in [
                                DecisionType.ADD.value,
                                DecisionType.DEPENDENCY_ADD.value,
                            ]
                        ):

                            ctx.rbar_ranges.append(
                                (
                                    start_addr,
                                    end_addr,
                                )
                            )

                        elif (
                            rbar_eval["decision"]
                            in [
                                DecisionType.DELETE.value,
                                DecisionType.DEPENDENCY_DELETE.value,
                            ]
                        ):

                            ctx.rbar_ranges = [
                                r
                                for r in (
                                    ctx.rbar_ranges
                                )
                                if r
                                != (
                                    start_addr,
                                    end_addr,
                                )
                            ]

                        elif (
                            rbar_eval["decision"]
                            == DecisionType.SUPERSEDE.value
                        ):

                            old_start, old_end = (
                                rbar_eval[
                                    "replace"
                                ]
                            )

                            # remove old
                            ctx.rbar_ranges = [
                                r
                                for r in (
                                    ctx.rbar_ranges
                                )
                                if r
                                != (
                                    old_start,
                                    old_end,
                                )
                            ]

                            # add new
                            ctx.rbar_ranges.append(
                                (
                                    start_addr,
                                    end_addr,
                                )
                            )

                            delete_eval = {
                                "decision": DecisionType.DELETE.value,
                                "reason": "Superseded by larger range",
                            }

                            delete_status = await create_status(
                                db,

                                entry_id=rbar_entry.id,

                                entry_type="RBAR",

                                inst=inst,

                                eval_result=delete_eval,
                            )

                            delete_detail = EntryInstanceDetail(
                                instance_status_id=delete_status.id,

                                entry_id=rbar_entry.id,

                                entry_type="RBAR",

                                dra_type=inst["dra_type"],

                                instance_label=inst["instance_label"],

                                start_addr=old_start,

                                end_addr=old_end,

                                raw_payload={
                                    "start_addr": old_start,
                                    "end_addr": old_end,
                                    "reason": "Superseded",
                                },
                            )

                            db.add(delete_detail)

            if row_skipped:
                skipped += 1
            else:
                processed += 1

        except Exception:
            failed += 1
            log=AuditLog(request_id=request.id,level="ERROR",message=str(ex),raw_payload=row,
                         )
            db.add(log)

        request.processed_rows = processed
        request.skipped_rows = skipped
        request.failed_rows = failed

    request.status = "COMPLETED"

    request.completed_at = datetime.utcnow()

    return {"status": "done"}