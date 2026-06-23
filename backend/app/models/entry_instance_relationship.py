import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.models.base import Base

class EntryInstanceRelationship(Base):
    __tablename__ = "entry_instance_relationships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_status_id = Column(String, ForeignKey("entry_instance_statuses.id"), nullable=False)
    related_request_id = Column(String, ForeignKey("change_requests.id"), nullable=False)
    relationship_type = Column(String, nullable=False)
    relationship_match_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "instance_status_id", 
            "related_request_id", 
            "relationship_type", 
            name="uq_entry_instance_relationship_fields"
        ),
        Index(
            "ix_entry_instance_relationship_fields",
            "instance_status_id",
            "related_request_id",
            "relationship_type"
        ),
    )