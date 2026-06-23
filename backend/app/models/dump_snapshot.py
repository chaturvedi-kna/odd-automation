import uuid
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.sql import func
from app.models.base import Base


class DumpSnapshot(Base):
    """
    Metadata record for one ingested dump file.
    The actual rows live in prr_dump_rows / rbar_dump_rows.
    """

    __tablename__ = "dump_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dra_type = Column(String, nullable=False)
    instance_label = Column(String, nullable=False)
    object_type = Column(String, nullable=False)       # "PRR" | "RBAR"
    file_name = Column(String, nullable=True)
    source_timestamp = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_dump_snapshot_lookup", "dra_type", "instance_label", "object_type"),
        Index("idx_dump_snapshot_created", "created_at"),
    )
