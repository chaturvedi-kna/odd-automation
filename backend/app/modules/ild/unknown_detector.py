"""
Unknown entry detector.

Scans in-scope dump rows and flags any that were not initiated by a request
in our system.  These are written as UnknownEntry records.
"""
import logging
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.prr_entry import PrrEntry
from app.models.rbar_entry import RbarEntry
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.unknown_entry import UnknownEntry
from app.models.enums import DecisionType
from app.core.config import settings

logger = logging.getLogger(__name__)


def _in_prr_scope(name: str) -> bool:
    suffixes = [s.strip().lower() for s in settings.PRR_SCOPE_SUFFIXES.split(",") if s.strip()]
    nl = name.lower()
    return any(nl.endswith(suf) or f"_{suf}" in nl for suf in suffixes)


def _in_rbar_scope(destination: str) -> bool:
    suffixes = [s.strip().lower() for s in settings.RBAR_SCOPE_SUFFIXES.split(",") if s.strip()]
    dl = (destination or "").lower()
    return any(dl.endswith(suf) for suf in suffixes)


def detect_unknown_prr(db: Session, dra_type: str, instance_label: str, snapshot) -> list[UnknownEntry]:
    """Return UnknownEntry records for PRR dump rows with no matching ADD request."""
    dump_rows = db.execute(
        select(PrrDumpRow).where(PrrDumpRow.snapshot_id == snapshot.id)
    ).scalars().all()

    # Build set of realms we know about (ADD decisions for this instance)
    known_realms: set[str] = set()
    statuses = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(
            and_(
                EntryInstanceStatus.dra_type == dra_type,
                EntryInstanceStatus.instance_label == instance_label,
                EntryInstanceStatus.entry_type == "PRR",
                EntryInstanceStatus.decision.in_([
                    DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value
                ]),
            )
        )
    ).all()
    for s, d in statuses:
        if d.realm:
            known_realms.add(d.realm.lower())

    # Also check existing unknowns to avoid duplicates
    existing = db.execute(
        select(UnknownEntry.identifier).where(
            and_(
                UnknownEntry.dra_type == dra_type,
                UnknownEntry.instance_label == instance_label,
                UnknownEntry.entry_type == "PRR",
            )
        )
    ).scalars().all()
    already_flagged = set(existing)

    unknowns = []
    for row in dump_rows:
        name = (row.name or "").strip()
        if not name or not _in_prr_scope(name):
            continue
        realm = (row.realm or "").strip().lower()
        if realm not in known_realms and realm not in already_flagged:
            logger.warning(
                "Unknown PRR entry detected: realm=%s name=%s on %s/%s",
                realm, name, dra_type, instance_label,
            )
            unknowns.append(UnknownEntry(
                dra_type=dra_type,
                instance_label=instance_label,
                entry_type="PRR",
                identifier=realm,
                raw_payload=row.raw_payload,
            ))
            already_flagged.add(realm)

    return unknowns


def detect_unknown_rbar(db: Session, dra_type: str, instance_label: str, snapshot) -> list[UnknownEntry]:
    """Return UnknownEntry records for RBAR dump rows with no matching ADD request."""
    dump_rows = db.execute(
        select(RbarDumpRow).where(RbarDumpRow.snapshot_id == snapshot.id)
    ).scalars().all()

    known_ranges: set[tuple] = set()
    statuses = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(
            and_(
                EntryInstanceStatus.dra_type == dra_type,
                EntryInstanceStatus.instance_label == instance_label,
                EntryInstanceStatus.entry_type == "RBAR",
                EntryInstanceStatus.decision.in_([
                    DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value
                ]),
            )
        )
    ).all()
    for s, d in statuses:
        if d.start_addr is not None and d.end_addr is not None:
            known_ranges.add((int(d.start_addr), int(d.end_addr)))

    existing = db.execute(
        select(UnknownEntry.identifier).where(
            and_(
                UnknownEntry.dra_type == dra_type,
                UnknownEntry.instance_label == instance_label,
                UnknownEntry.entry_type == "RBAR",
            )
        )
    ).scalars().all()
    already_flagged = set(existing)

    unknowns = []
    for row in dump_rows:
        if row.start_addr is None:
            continue
        dest = (row.destination or "").strip()
        if not _in_rbar_scope(dest):
            continue
        try:
            rk = (int(row.start_addr), int(row.end_addr))
        except (TypeError, ValueError):
            continue
        key_str = f"{rk[0]}-{rk[1]}"
        if rk not in known_ranges and key_str not in already_flagged:
            logger.warning(
                "Unknown RBAR entry detected: %s-%s on %s/%s",
                rk[0], rk[1], dra_type, instance_label,
            )
            unknowns.append(UnknownEntry(
                dra_type=dra_type,
                instance_label=instance_label,
                entry_type="RBAR",
                identifier=key_str,
                raw_payload=row.raw_payload,
            ))
            already_flagged.add(key_str)

    return unknowns
