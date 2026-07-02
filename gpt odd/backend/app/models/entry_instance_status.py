import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func

from app.models.base import Base


class EntryInstanceStatus(Base):
    __tablename__ = "entry_instance_statuses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    entry_id = Column(String, nullable=False)
    entry_type = Column(String, nullable=False)

    dra_type = Column(String, nullable=False)
    instance_label = Column(String, nullable=False)

    decision = Column(String)  # ADD / DELETE / SKIPPED / SUPERSEDE
    reason = Column(String)

    impl_status = Column(String, nullable=False)

    dependency_request_id = Column(
        String,
        ForeignKey("change_requests.id"),
        nullable=True,
    )
    dependency_note = Column(String, nullable=True)

    last_reconciled_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "entry_id",
            "entry_type",
            "dra_type",
            "instance_label",
            name="uq_entry_instance_status",
        ),
        Index(
            "idx_instance_status_lookup",
            "dra_type",
            "instance_label",
        ),
        Index(
            "idx_instance_status_impl",
            "entry_type",
            "impl_status",
        ),
        Index(
            "idx_instance_status_reconciled",
            "last_reconciled_at",
        ),
    )