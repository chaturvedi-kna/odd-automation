import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class PrrEntry(Base):
    """One PRR entry per input CSV row (realm / prt_rule)."""

    __tablename__ = "prr_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, ForeignKey("change_requests.id"), nullable=False)

    # CSV columns
    country = Column(String, nullable=True)
    operator = Column(String, nullable=True)
    mcc = Column(String, nullable=True)
    mnc = Column(String, nullable=True)
    realm = Column(String, nullable=True)
    prt_rule = Column(String, nullable=True)
    action = Column(String, nullable=False, default="ADD")   # ADD | DELETE

    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_prr_entry_request", "request_id"),
        Index("idx_prr_entry_realm", "realm"),
    )
