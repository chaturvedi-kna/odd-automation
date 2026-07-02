from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.enums import ImplStatus


async def create_instance_records(
    db,
    entry,
    entry_type,
    dra_type,
    instance_label,
    detail_payload,
    dependency_note=None,
    dependency_request_id=None,
):
    status = EntryInstanceStatus(
        entry_id=entry.id,
        entry_type=entry_type,
        dra_type=dra_type,
        instance_label=instance_label,
        impl_status=ImplStatus.PENDING.value,
        dependency_note=dependency_note,
        dependency_request_id=dependency_request_id,
    )

    db.add(status)
    await db.flush()

    detail = EntryInstanceDetail(
        instance_status_id=status.id,
        entry_id=entry.id,
        entry_type=entry_type,
        dra_type=dra_type,
        instance_label=instance_label,
        final_prt_rule=detail_payload.get("final_prt_rule"),
        realm=detail_payload.get("realm"),
        start_addr=detail_payload.get("start_addr"),
        end_addr=detail_payload.get("end_addr"),
        destination=detail_payload.get("destination"),
        raw_payload=detail_payload,
    )

    db.add(detail)