import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(
        String, ForeignKey("change_requests.id"), nullable=True   # nullable: reconciler logs have no request
    )
    level = Column(String, nullable=False, default="INFO")       # INFO | WARNING | ERROR | DEBUG
    entry_type = Column(String, nullable=True)                   # PRR | RBAR | ROW
    message = Column(String, nullable=True)
    instance_label = Column(String, nullable=True)
    dra_type = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_request", "request_id"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_level", "level"),
    )
