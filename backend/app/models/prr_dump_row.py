import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class PrrDumpRow(Base):
    """One in-scope PRR row from an ingested dump file."""

    __tablename__ = "prr_dump_rows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(String, ForeignKey("dump_snapshots.id"), nullable=False)

    name = Column(String, nullable=True)             # PRR rule name
    realm = Column(String, nullable=True)            # value_1 in dump
    route_list_name = Column(String, nullable=True)
    peer_route_table = Column(String, nullable=True)

    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_prr_row_snapshot", "snapshot_id"),
        Index("idx_prr_row_realm", "realm"),
    )
