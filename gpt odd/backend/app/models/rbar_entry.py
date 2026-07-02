import uuid
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class RbarEntry(Base):
    __tablename__ = "rbar_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    request_id = Column(String, ForeignKey("change_requests.id"), nullable=False)

    realm = Column(String, nullable=False)

    start_addr = Column(BigInteger, nullable=False)
    end_addr = Column(BigInteger, nullable=False)

    action = Column(String, nullable=False)

    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_rbar_range", "start_addr", "end_addr"),
    )