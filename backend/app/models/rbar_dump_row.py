import uuid
from sqlalchemy import Column, String, DateTime, BigInteger, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class RbarDumpRow(Base):
    """One in-scope RBAR row from an ingested dump file."""

    __tablename__ = "rbar_dump_rows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(String, ForeignKey("dump_snapshots.id"), nullable=False)

    table_name = Column(String, nullable=True)
    start_addr = Column(BigInteger, nullable=True)   # ALWAYS int — parsed via int(float()); never stored as float
    end_addr = Column(BigInteger, nullable=True)     # ALWAYS int — parsed via int(float()); never stored as float
    destination = Column(String, nullable=True)
    pfx_length = Column(String, nullable=True)
    old_table_name = Column(String, nullable=True)
    old_start_addr = Column(BigInteger, nullable=True)
    old_pfx_length = Column(String, nullable=True)

    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_rbar_row_snapshot", "snapshot_id"),
        Index("idx_rbar_row_range", "start_addr", "end_addr"),
    )
