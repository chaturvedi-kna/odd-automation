import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class EntryInstanceStatus(Base):
    __tablename__ = "entry_instance_statuses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    request_id = Column(
        String, ForeignKey("change_requests.id", ondelete="CASCADE"), nullable=False
    )

    entry_id = Column(String, nullable=False)
    entry_type = Column(String, nullable=False)

    dra_type = Column(String, nullable=False)
    instance_label = Column(String, nullable=False)

    decision = Column(String, nullable=True)   # ADD / DELETE / SKIPPED / SUPERSEDE / DEPENDENCY_*
    reason = Column(String, nullable=True)
    dependency_note = Column(String, nullable=True)

    impl_status = Column(String, nullable=True)  # FIX: was nullable=False – SKIPPED entries have no impl_status

    last_reconciled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    details = relationship("EntryInstanceDetail", backref="instance_status", lazy="raise")

    __table_args__ = (
        # NOTE: former UniqueConstraint("entry_id","entry_type","dra_type","instance_label")
        # was dropped (migration 0004): SUPERSEDE legitimately creates a second
        # status row (implicit DELETE) for the same entry+instance.
        Index("idx_instance_status_entry", "entry_id", "entry_type", "dra_type", "instance_label"),
        Index("idx_instance_status_lookup", "dra_type", "instance_label"),
        Index("idx_instance_status_impl", "entry_type", "impl_status"),
        Index("idx_instance_status_reconciled", "last_reconciled_at"),
        Index("idx_instance_status_request", "request_id"), 
    )