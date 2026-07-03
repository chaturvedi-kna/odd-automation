import uuid
from sqlalchemy import Column, String, DateTime, Boolean, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class UnknownEntry(Base):
    __tablename__ = "unknown_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    dra_type = Column(String, nullable=False)
    instance_label = Column(String, nullable=False)
    entry_type = Column(String, nullable=False)    # PRR | RBAR

    # For PRR: realm.  For RBAR: "start-end"
    identifier = Column(String, nullable=False)

    is_acknowledged = Column(Boolean, nullable=False, default=False)

    raw_payload = Column(JSONB, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dra_type", "instance_label", "entry_type", "identifier",
                         name="uq_unknown_entry"),
        Index("idx_unknown_entry_instance", "dra_type", "instance_label"),
        Index("idx_unknown_entry_ack", "is_acknowledged"),
    )
