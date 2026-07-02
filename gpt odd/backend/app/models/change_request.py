import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.models.base import Base


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    module = Column(String, nullable=False)
    status = Column(String, nullable=False)

    request_version = Column(Integer, nullable=False, default=1)
    uploaded_file_name = Column(String, nullable=True)

    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    skipped_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)

    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)