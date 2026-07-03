"""
Master ODD viewer API — JSON version of the Master ODD excel simulation:
latest dump snapshot rows merged with PENDING / AWAITING_IMPLEMENTATION
changes for one DRA instance, with filtering + sorting for the UI.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db
from app.api.deps.auth import get_current_user
from app.core.config import settings
from app.models.dump_snapshot import DumpSnapshot
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.enums import DecisionType, ImplStatus

router = APIRouter(prefix="/master-odd", tags=["master-odd"])

ADD_DECISIONS = {DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value}
DEL_DECISIONS = {
    DecisionType.DELETE.value,
    DecisionType.DEPENDENCY_DELETE.value,
    DecisionType.SUPERSEDE.value,
    DecisionType.SUPERSEDE_PENDING.value,
}
PENDING_IMPL = [ImplStatus.PENDING.value, ImplStatus.AWAITING_IMPLEMENTATION.value]

PRR_SORT_FIELDS = {"name", "realm", "route_list_name", "peer_route_table", "source"}
RBAR_SORT_FIELDS = {"table_name", "start_addr", "end_addr", "destination", "source"}


async def _latest_snapshot(db, dra_type, instance_label, obj_type):
    return (await db.execute(
        select(DumpSnapshot).where(and_(
            DumpSnapshot.dra_type == dra_type,
            DumpSnapshot.instance_label == instance_label,
            DumpSnapshot.object_type == obj_type,
        )).order_by(DumpSnapshot.created_at.desc()).limit(1)
    )).scalars().first()


async def _pending(db, dra_type, instance_label, entry_type):
    return (await db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(and_(
            EntryInstanceStatus.dra_type == dra_type,
            EntryInstanceStatus.instance_label == instance_label,
            EntryInstanceStatus.entry_type == entry_type,
            EntryInstanceStatus.impl_status.in_(PENDING_IMPL),
        )).order_by(EntryInstanceStatus.created_at.asc())
    )).all()


@router.get("/")
async def master_odd(
    dra_type: str,
    instance_label: str,
    object_type: str = "PRR",
    search: str = "",
    source: str = "",            # DUMP | PENDING_ADD | PENDING_DELETE | "" (all)
    sort_by: str = "",
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    object_type = object_type.upper()
    if object_type not in ("PRR", "RBAR"):
        raise HTTPException(400, "object_type must be PRR or RBAR")
    page_size = min(max(1, page_size), settings.MAX_PAGE_SIZE)

    snap = await _latest_snapshot(db, dra_type, instance_label, object_type)
    pending = await _pending(db, dra_type, instance_label, object_type)

    rows: list[dict] = []

    if object_type == "PRR":
        del_realms = {
            (d.realm or "").lower()
            for s, d in pending if d.realm and s.decision in DEL_DECISIONS
        }
        if snap:
            dump_rows = (await db.execute(
                select(PrrDumpRow).where(PrrDumpRow.snapshot_id == snap.id)
            )).scalars().all()
            for r in dump_rows:
                rows.append({
                    "name": r.name,
                    "realm": r.realm,
                    "route_list_name": r.route_list_name,
                    "peer_route_table": r.peer_route_table,
                    "source": "PENDING_DELETE" if (r.realm or "").lower() in del_realms else "DUMP",
                })
        for s, d in pending:
            if s.decision in ADD_DECISIONS:
                rows.append({
                    "name": d.final_prt_rule,
                    "realm": d.realm,
                    "route_list_name": (d.raw_payload or {}).get("routeListName"),
                    "peer_route_table": (d.raw_payload or {}).get("peerRouteTable"),
                    "source": "PENDING_ADD",
                })
    else:
        del_ranges = {
            (int(d.start_addr), int(d.end_addr))
            for s, d in pending
            if d.start_addr is not None and d.end_addr is not None and s.decision in DEL_DECISIONS
        }
        if snap:
            dump_rows = (await db.execute(
                select(RbarDumpRow).where(RbarDumpRow.snapshot_id == snap.id)
            )).scalars().all()
            for r in dump_rows:
                key = (int(r.start_addr), int(r.end_addr)) if r.start_addr is not None and r.end_addr is not None else None
                rows.append({
                    "table_name": r.table_name,
                    # IMSI bounds as strings: 15-digit ints exceed JS safe-integer precision
                    "start_addr": str(r.start_addr) if r.start_addr is not None else None,
                    "end_addr": str(r.end_addr) if r.end_addr is not None else None,
                    "destination": r.destination,
                    "source": "PENDING_DELETE" if key in del_ranges else "DUMP",
                })
        for s, d in pending:
            if s.decision in ADD_DECISIONS and d.start_addr is not None:
                rows.append({
                    "table_name": (d.raw_payload or {}).get("tableName"),
                    "start_addr": str(d.start_addr),
                    "end_addr": str(d.end_addr) if d.end_addr is not None else None,
                    "destination": d.destination,
                    "source": "PENDING_ADD",
                })

    # ── Filters ────────────────────────────────────────────────────────────
    if source:
        rows = [r for r in rows if r["source"] == source.upper()]
    if search:
        needle = search.lower()
        rows = [
            r for r in rows
            if any(needle in str(v or "").lower() for k, v in r.items() if k != "source")
        ]

    # ── Sorting ────────────────────────────────────────────────────────────
    valid_fields = PRR_SORT_FIELDS if object_type == "PRR" else RBAR_SORT_FIELDS
    if sort_by:
        if sort_by not in valid_fields:
            raise HTTPException(400, f"sort_by must be one of {', '.join(sorted(valid_fields))}")
        numeric = sort_by in ("start_addr", "end_addr")

        def key(r):
            v = r.get(sort_by)
            if v is None:
                return (1, 0 if numeric else "")
            return (0, int(v) if numeric else str(v).lower())

        rows.sort(key=key, reverse=(sort_dir.lower() == "desc"))

    total = len(rows)
    start = (page - 1) * page_size
    return {
        "dra_type": dra_type,
        "instance_label": instance_label,
        "object_type": object_type,
        "snapshot": {
            "id": snap.id,
            "file_name": snap.file_name,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
            "source_timestamp": snap.source_timestamp.isoformat() if snap.source_timestamp else None,
        } if snap else None,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": rows[start:start + page_size],
    }
