import uuid
from sqlalchemy import Column, String, DateTime, BigInteger, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class RbarEntry(Base):
    """One RBAR entry per input CSV row (IMSI address range)."""

    __tablename__ = "rbar_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, ForeignKey("change_requests.id"), nullable=False)

    realm = Column(String, nullable=True)
    start_addr = Column(BigInteger, nullable=True)
    end_addr = Column(BigInteger, nullable=True)
    action = Column(String, nullable=False, default="ADD")   # ADD | DELETE

    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_rbar_entry_request", "request_id"),
        Index("idx_rbar_entry_range", "start_addr", "end_addr"),
    )
