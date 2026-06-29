## TODO

## Replay supersede from relationship/replace metadata.

import logging
import re
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.prr_dump_row import PrrDumpRow
from app.models.rbar_dump_row import RbarDumpRow
from app.models.entry_instance_status import EntryInstanceStatus
from app.models.entry_instance_detail import EntryInstanceDetail
from app.models.unknown_entry import UnknownEntry
from app.models.enums import DecisionType, ImplStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

PRR_SCOPE_SUFFIXES = [s.strip().lower() for s in settings.PRR_SCOPE_SUFFIXES.split(",") if s.strip()]
RBAR_SCOPE_SUFFIXES = [s.strip().lower() for s in settings.RBAR_SCOPE_SUFFIXES.split(",") if s.strip()]

ADD_DECISIONS = {DecisionType.ADD.value, DecisionType.DEPENDENCY_ADD.value}
DEL_DECISIONS = {DecisionType.DELETE.value, DecisionType.DEPENDENCY_DELETE.value}
SUPERSEDE_DECISIONS = {DecisionType.SUPERSEDE.value, DecisionType.SUPERSEDE_PENDING.value}


def _in_prr_scope(name: str) -> bool:
    nl = name.lower()
    return any(nl.endswith(suf) or f"_{suf}" in nl for suf in PRR_SCOPE_SUFFIXES)


def _in_rbar_scope(destination: str) -> bool:
    dl = (destination or "").lower()
    return any(dl.endswith(suf) for suf in RBAR_SCOPE_SUFFIXES)


def _normalize_string(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


# ── Chronological History Replay Loaders ───────────────────────────────

def _load_effective_prr(db: Session, dra_type: str, instance_label: str) -> set[tuple[str, str]]:
    effective_state: dict[str, str] = {}

    statuses = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(
            and_(
                EntryInstanceStatus.dra_type == dra_type,
                EntryInstanceStatus.instance_label == instance_label,
                EntryInstanceStatus.entry_type == "PRR",
                EntryInstanceStatus.impl_status == ImplStatus.IMPLEMENTED.value
            )
        ).order_by(EntryInstanceStatus.created_at.asc(), EntryInstanceStatus.id.asc())
    ).all()

    for s, d in statuses:
        realm = _normalize_string(d.realm)
        rule = _normalize_string(d.final_prt_rule)
        if not realm:
            continue

        if s.decision in ADD_DECISIONS or s.decision in SUPERSEDE_DECISIONS:
            effective_state[realm] = rule
        elif s.decision in DEL_DECISIONS:
            effective_state.pop(realm, None)

    return {(realm, rule) for realm, rule in effective_state.items()}


def _load_effective_rbar(db: Session, dra_type: str, instance_label: str) -> set[tuple[int, int, str]]:
    """
    Fixed RBAR Replay Engine:
    Dynamically clears out superseded or overlapping sub-ranges when a wider block is processed.
    """
    # Key: (start_addr, end_addr) -> Value: destination
    effective_state: dict[tuple[int, int], str] = {}

    statuses = db.execute(
        select(EntryInstanceStatus, EntryInstanceDetail)
        .join(EntryInstanceDetail, EntryInstanceDetail.instance_status_id == EntryInstanceStatus.id)
        .where(
            and_(
                EntryInstanceStatus.dra_type == dra_type,
                EntryInstanceStatus.instance_label == instance_label,
                EntryInstanceStatus.entry_type == "RBAR",
                EntryInstanceStatus.impl_status == ImplStatus.IMPLEMENTED.value
            )
        ).order_by(EntryInstanceStatus.created_at.asc(), EntryInstanceStatus.id.asc())
    ).all()

    for s, d in statuses:
        if d.start_addr is None or d.end_addr is None:
            continue
            
        new_start = int(d.start_addr)
        new_end = int(d.end_addr)
        new_rk = (new_start, new_end)
        dest = _normalize_string(d.destination)

        if s.decision in ADD_DECISIONS or s.decision in SUPERSEDE_DECISIONS:
            # ── FIXED: Clear out any pre-existing ranges swallowed by this supersede/addition ──
            overridden_keys = [
                old_rk for old_rk in effective_state.keys()
                if (old_rk[0] >= new_start and old_rk[1] <= new_end)  # Nested sub-range matching
            ]
            for old_rk in overridden_keys:
                effective_state.pop(old_rk, None)

            effective_state[new_rk] = dest

        elif s.decision in DEL_DECISIONS:
            effective_state.pop(new_rk, None)

    return {(rk[0], rk[1], dest) for rk, dest in effective_state.items()}


# ── Core Detectors ─────────────────────────────────────────────────────

def detect_unknown_prr(db: Session, dra_type: str, instance_label: str, snapshot) -> list[UnknownEntry]:
    dump_rows = db.execute(select(PrrDumpRow).where(PrrDumpRow.snapshot_id == snapshot.id)).scalars().all()
    effective_prr = _load_effective_prr(db, dra_type, instance_label)

    existing = db.execute(
        select(UnknownEntry.identifier).where(
            and_(
                UnknownEntry.dra_type == dra_type,
                UnknownEntry.instance_label == instance_label,
                UnknownEntry.entry_type == "PRR",
                UnknownEntry.snapshot_id == snapshot.id
            )
        )
    ).scalars().all()
    already_flagged = set(existing)

    unknowns = []
    for row in dump_rows:
        name = (row.name or "").strip()
        if not name or not _in_prr_scope(name):
            continue
            
        realm = _normalize_string(row.realm)
        rule_name = _normalize_string(name)
        
        config_key = (realm, rule_name)
        lookup_identifier = f"{realm}:{rule_name}"

        if config_key not in effective_prr and lookup_identifier not in already_flagged:
            logger.warning(
                "Unknown PRR entry detected via timeline replay: realm=%s name=%s on %s/%s",
                realm, name, dra_type, instance_label,
            )
            unknowns.append(UnknownEntry(
                dra_type=dra_type,
                instance_label=instance_label,
                entry_type="PRR",
                snapshot_id=snapshot.id,
                identifier=lookup_identifier,
                raw_payload=row.raw_payload,
            ))
            already_flagged.add(lookup_identifier)

    return unknowns


def detect_unknown_rbar(db: Session, dra_type: str, instance_label: str, snapshot) -> list[UnknownEntry]:
    dump_rows = db.execute(select(RbarDumpRow).where(RbarDumpRow.snapshot_id == snapshot.id)).scalars().all()
    effective_rbar = _load_effective_rbar(db, dra_type, instance_label)

    existing = db.execute(
        select(UnknownEntry.identifier).where(
            and_(
                UnknownEntry.dra_type == dra_type,
                UnknownEntry.instance_label == instance_label,
                UnknownEntry.entry_type == "RBAR",
                UnknownEntry.snapshot_id == snapshot.id
            )
        )
    ).scalars().all()
    already_flagged = set(existing)

    unknowns = []
    for row in dump_rows:
        if row.start_addr is None or row.end_addr is None:
            continue
            
        dest = (row.destination or "").strip()
        if not _in_rbar_scope(dest):
            continue
            
        try:
            start_i = int(row.start_addr)
            end_i = int(row.end_addr)
        except (TypeError, ValueError) as ex:
            logger.warning(
                "Malformed RBAR row parsed in snapshot %s. Start: %s, End: %s. Error: %s",
                snapshot.id, row.start_addr, row.end_addr, ex
            )
            continue
            
        dest_norm = _normalize_string(dest)
        config_key = (start_i, end_i, dest_norm)
        lookup_identifier = f"{start_i}-{end_i}:{dest_norm}"

        if config_key not in effective_rbar and lookup_identifier not in already_flagged:
            logger.warning(
                "Unknown RBAR entry detected via timeline replay: range=%s-%s destination=%s on %s/%s",
                start_i, end_i, dest, dra_type, instance_label,
            )
            unknowns.append(UnknownEntry(
                dra_type=dra_type,
                instance_label=instance_label,
                entry_type="RBAR",
                snapshot_id=snapshot.id,
                identifier=lookup_identifier,
                raw_payload=row.raw_payload,
            ))
            already_flagged.add(lookup_identifier)

    return unknowns