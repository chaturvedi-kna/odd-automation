import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String, nullable=False)    # REQUEST_DONE | RECONCILED | UNKNOWN_DETECTED | ROLLBACK
    message = Column(String, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    related_request_id = Column(
        String, ForeignKey("change_requests.id"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_notification_unread", "is_read", "created_at"),
    )
