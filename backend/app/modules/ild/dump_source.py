"""
Pluggable dump source abstraction.

Today the DRA system dumps land in folders on the VM; later this may change
(SFTP, object storage, API pull …). Implement a new source class and register
it in ``SOURCES`` — nothing else in the pipeline changes.

Configured via config.py:
    DUMP_SOURCE_TYPE    = "folder"           (only built-in today)
    DUMP_SOURCE_LAYOUT  = "nested" | "flat"
    DUMP_INCOMING_PATH  = base folder scanned by the folder source

Layouts:
    nested : {DUMP_INCOMING_PATH}/{dra_type}/{instance_label}/<file>.csv
    flat   : all files directly in DUMP_INCOMING_PATH; instance resolved from
             the filename via DUMP_FILENAME_INSTANCE_REGEX named groups
             (?P<dra_type>…) and (?P<instance_label>…). Files that don't
             match are left in place and reported.
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DumpFile:
    path: str
    dra_type: str
    instance_label: str
    filename: str


class DumpSource(Protocol):
    def iter_files(self) -> Iterator[DumpFile]: ...


class FolderDumpSource:
    """Scans DUMP_INCOMING_PATH on the local filesystem / mounted volume."""

    def __init__(self, base_path: str | None = None, layout: str | None = None):
        self.base = Path(base_path or settings.DUMP_INCOMING_PATH)
        self.layout = (layout or settings.DUMP_SOURCE_LAYOUT).lower()

    def iter_files(self) -> Iterator[DumpFile]:
        if not self.base.exists():
            logger.warning("Dump incoming path does not exist: %s", self.base)
            return

        if self.layout == "nested":
            # {base}/{dra_type}/{instance_label}/file.csv
            for dra_dir in sorted(p for p in self.base.iterdir() if p.is_dir()):
                for inst_dir in sorted(p for p in dra_dir.iterdir() if p.is_dir()):
                    for f in sorted(inst_dir.glob("*.csv")):
                        yield DumpFile(
                            path=str(f),
                            dra_type=dra_dir.name,
                            instance_label=inst_dir.name,
                            filename=f.name,
                        )
        elif self.layout == "flat":
            pattern = getattr(settings, "DUMP_FILENAME_INSTANCE_REGEX", "") or ""
            rx = re.compile(pattern) if pattern else None
            for f in sorted(self.base.glob("*.csv")):
                if not rx:
                    logger.warning(
                        "Flat dump layout requires DUMP_FILENAME_INSTANCE_REGEX; skipping %s",
                        f.name,
                    )
                    continue
                m = rx.search(f.name)
                if not m:
                    logger.warning("Dump filename does not match instance regex, skipping: %s", f.name)
                    continue
                yield DumpFile(
                    path=str(f),
                    dra_type=m.groupdict().get("dra_type", "V-DRA"),
                    instance_label=m.groupdict().get("instance_label", ""),
                    filename=f.name,
                )
        else:
            logger.warning("Unknown DUMP_SOURCE_LAYOUT '%s' — nothing scanned", self.layout)


SOURCES = {
    "folder": FolderDumpSource,
}


def get_dump_source() -> DumpSource:
    source_cls = SOURCES.get(settings.DUMP_SOURCE_TYPE.lower())
    if not source_cls:
        raise ValueError(
            f"Unknown DUMP_SOURCE_TYPE '{settings.DUMP_SOURCE_TYPE}'. "
            f"Available: {', '.join(SOURCES)}"
        )
    return source_cls()
