import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    entry_type = Column(String, nullable=True)
    level = Column(String, nullable=False)
    message = Column(String, nullable=False)

    request_id = Column(
        String,
        ForeignKey("change_requests.id"),
        nullable=True,
    )

    instance_label = Column(String, nullable=True)
    dra_type = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_log_created", "created_at"),
        Index("idx_audit_log_request", "request_id"),
    )