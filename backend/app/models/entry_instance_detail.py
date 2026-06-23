import uuid
from sqlalchemy import Column, String, DateTime, BigInteger, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class EntryInstanceDetail(Base):
    """
    Resolved configuration payload for one entry on one DRA instance.
    Created only for actionable decisions (ADD / DELETE / SUPERSEDE / DEPENDENCY_*).
    """

    __tablename__ = "entry_instance_details"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_status_id = Column(
        String, ForeignKey("entry_instance_statuses.id"), nullable=False
    )
    entry_id = Column(String, nullable=False)
    entry_type = Column(String, nullable=False)   # PRR | RBAR
    dra_type = Column(String, nullable=False)
    instance_label = Column(String, nullable=False)

    # PRR-specific
    final_prt_rule = Column(String, nullable=True)
    realm = Column(String, nullable=True)

    # RBAR-specific
    start_addr = Column(BigInteger, nullable=True)
    end_addr = Column(BigInteger, nullable=True)
    destination = Column(String, nullable=True)

    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_detail_status_id", "instance_status_id"),
        Index("idx_detail_entry", "entry_id", "entry_type"),
        Index("idx_detail_realm", "realm"),
    )
