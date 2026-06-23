"""
Exporter module.

delta_excel(db, request_id, out_path)
    → Excel workbook with one sheet per (dra_type, instance_label) combination,
      listing all actionable entries from the request.

master_odd_excel(db, request_id, instance_label, dra_type, out_path)
    → Excel workbook representing the current Master ODD for one instance:
      latest dump rows + pending ADDs added + pending DELETEs removed.
"""
import logging
from pathlib import Path
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.dump_snapshot import DumpSnapshot
from app.models.enums import DecisionType

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF")
ADD_FILL = PatternFill("solid", fgColor="C6EFCE")
DEL_FILL = PatternFill("solid", fgColor="FFC7CE")
DEP_FILL = PatternFill("solid", fgColor="FFEB9C")

ADD_DECISIONS = {DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value}
DEL_DECISIONS = {DecisionType.DELETE.value, DecisionType.DEPENDENCY_DELETE.value,
                 DecisionType.SUPERSEDE.value}


def _style_header(ws, headers: list[str]):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"


def _auto_width(ws):
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 50)


def _row_fill(decision: str) -> PatternFill | None:
    if decision in ADD_DECISIONS:
        return ADD_FILL
    if decision in DEL_DECISIONS:
        return DEL_FILL
    return DEP_FILL


def delta_excel(db: Session, request_id: str, out_path: str) -> str:
    """
    Generate a Delta Excel file for the given request.
    Returns the final file path.
    """
    # Load all actionable statuses for this request
    rows = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .join(PrrEntry, PrrEntry.id == EntryInstanceStatus.entry_id, isouter=True)
        .where(
            and_(
                EntryInstanceStatus.decision.in_(
                    list(ADD_DECISIONS | DEL_DECISIONS)
                    + [DecisionType.DEPENDENCY_ADD.value, DecisionType.DEPENDENCY_DELETE.value,
                       DecisionType.SUPERSEDE.value]
                ),
            )
        )
    ).all()

    # Also load PRR/RBAR entries for this request
    prr_entries = {
        e.id: e for e in db.execute(
            select(PrrEntry).where(PrrEntry.request_id == request_id)
        ).scalars().all()
    }
    rbar_entries = {
        e.id: e for e in db.execute(
            select(RbarEntry).where(RbarEntry.request_id == request_id)
        ).scalars().all()
    }

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Group by instance
    by_instance: dict[str, list] = {}
    for status, detail in rows:
        # Check belongs to this request
        if status.entry_type == "PRR" and status.entry_id not in prr_entries:
            continue
        if status.entry_type == "RBAR" and status.entry_id not in rbar_entries:
            continue
        key = f"{status.dra_type}_{status.instance_label}"
        by_instance.setdefault(key, []).append((status, detail))

    if not by_instance:
        # Create empty sheet
        ws = wb.create_sheet("No Data")
        ws["A1"] = "No actionable entries found for this request."
    else:
        for sheet_name, entries in by_instance.items():
            ws = wb.create_sheet(sheet_name[:31])  # Excel limit

            # Detect what types are in this sheet
            has_prr = any(s.entry_type == "PRR" for s, _ in entries)
            has_rbar = any(s.entry_type == "RBAR" for s, _ in entries)

            headers = ["Type", "Action/Decision", "Realm", "PRT Rule / Final Rule",
                       "Range Start", "Range End", "Destination", "Dependency Note", "Impl Status"]
            _style_header(ws, headers)

            for row_idx, (status, detail) in enumerate(entries, 2):
                fill = _row_fill(status.decision)
                vals = [
                    status.entry_type,
                    status.decision,
                    detail.realm or "",
                    detail.final_prt_rule or "",
                    str(detail.start_addr) if detail.start_addr else "",
                    str(detail.end_addr) if detail.end_addr else "",
                    detail.destination or "",
                    status.dependency_note or "",
                    status.impl_status or "N/A",
                ]
                for col, val in enumerate(vals, 1):
                    cell = ws.cell(row=row_idx, column=col, value=val)
                    if fill:
                        cell.fill = fill

            _auto_width(ws)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    logger.info("Delta Excel saved: %s", out_path)
    return out_path


def master_odd_excel(
    db: Session,
    dra_type: str,
    instance_label: str,
    out_path: str,
) -> str:
    """
    Generate the Master ODD Excel for one instance:
    latest dump + all PENDING ADDs applied + all PENDING DELETEs removed.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ── PRR sheet ──────────────────────────────────────────────────────────
    prr_ws = wb.create_sheet("PRR_PeerRouteRule")
    prr_headers = ["name", "realm", "routeListName", "peerRouteTable", "Source"]
    _style_header(prr_ws, prr_headers)

    prr_snap = db.execute(
        select(DumpSnapshot).where(
            and_(DumpSnapshot.dra_type == dra_type,
                 DumpSnapshot.instance_label == instance_label,
                 DumpSnapshot.object_type == "PRR")
        ).order_by(DumpSnapshot.created_at.desc()).limit(1)
    ).scalars().first()

    base_prr: list[dict] = []
    if prr_snap:
        rows = db.execute(
            select(PrrDumpRow).where(PrrDumpRow.snapshot_id == prr_snap.id)
        ).scalars().all()
        base_prr = [{"name": r.name, "realm": r.realm,
                     "routeListName": r.route_list_name,
                     "peerRouteTable": r.peer_route_table} for r in rows]

    # Apply pending changes
    pending = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(and_(
            EntryInstanceStatus.dra_type == dra_type,
            EntryInstanceStatus.instance_label == instance_label,
            EntryInstanceStatus.entry_type == "PRR",
            EntryInstanceStatus.impl_status == "PENDING FOR RECONCILIATION",
        ))
    ).all()

    del_realms = {d.realm.lower() for s, d in pending if d.realm and s.decision in DEL_DECISIONS}
    add_rows = [(s, d) for s, d in pending if s.decision in ADD_DECISIONS]

    final_prr = [r for r in base_prr if (r.get("realm") or "").lower() not in del_realms]
    for s, d in add_rows:
        final_prr.append({
            "name": d.final_prt_rule or "",
            "realm": d.realm or "",
            "routeListName": "",
            "peerRouteTable": "",
        })

    for row_idx, row in enumerate(final_prr, 2):
        source = "DUMP" if row_idx - 2 < len(base_prr) else "PENDING"
        vals = [row.get("name"), row.get("realm"), row.get("routeListName"),
                row.get("peerRouteTable"), source]
        for col, val in enumerate(vals, 1):
            prr_ws.cell(row=row_idx, column=col, value=val)
    _auto_width(prr_ws)

    # ── RBAR sheet ─────────────────────────────────────────────────────────
    rbar_ws = wb.create_sheet("RBAR_AddressRange")
    rbar_headers = ["tableName", "startAddr", "endAddr", "destination", "Source"]
    _style_header(rbar_ws, rbar_headers)

    rbar_snap = db.execute(
        select(DumpSnapshot).where(
            and_(DumpSnapshot.dra_type == dra_type,
                 DumpSnapshot.instance_label == instance_label,
                 DumpSnapshot.object_type == "RBAR")
        ).order_by(DumpSnapshot.created_at.desc()).limit(1)
    ).scalars().first()

    base_rbar: list[dict] = []
    if rbar_snap:
        rows = db.execute(
            select(RbarDumpRow).where(RbarDumpRow.snapshot_id == rbar_snap.id)
        ).scalars().all()
        base_rbar = [{"tableName": r.table_name, "startAddr": int(r.start_addr),
                      "endAddr": int(r.end_addr), "destination": r.destination}
                     for r in rows if r.start_addr]

    pending_rbar = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(and_(
            EntryInstanceStatus.dra_type == dra_type,
            EntryInstanceStatus.instance_label == instance_label,
            EntryInstanceStatus.entry_type == "RBAR",
            EntryInstanceStatus.impl_status == "PENDING FOR RECONCILIATION",
        ))
    ).all()

    del_ranges = {
        (int(d.start_addr), int(d.end_addr))
        for s, d in pending_rbar
        if d.start_addr and s.decision in DEL_DECISIONS
    }
    add_rbar = [(s, d) for s, d in pending_rbar if s.decision in ADD_DECISIONS]

    final_rbar = [r for r in base_rbar if (r["startAddr"], r["endAddr"]) not in del_ranges]
    for s, d in add_rbar:
        final_rbar.append({
            "tableName": "IMSI",
            "startAddr": int(d.start_addr),
            "endAddr": int(d.end_addr),
            "destination": d.destination or "",
        })

    for row_idx, row in enumerate(final_rbar, 2):
        source = "DUMP" if row_idx - 2 < len(base_rbar) else "PENDING"
        vals = [row.get("tableName"), str(row.get("startAddr")),
                str(row.get("endAddr")), row.get("destination"), source]
        for col, val in enumerate(vals, 1):
            rbar_ws.cell(row=row_idx, column=col, value=val)
    _auto_width(rbar_ws)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    logger.info("Master ODD Excel saved: %s", out_path)
    return out_path
