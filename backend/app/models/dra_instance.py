import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func
from app.models.base import Base


class DRAInstance(Base):
    __tablename__ = "dra_instances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dra_type = Column(String, nullable=False)          # "BM-DRA" | "V-DRA"
    site = Column(String, nullable=False)              # e.g. "DEL", "MUM"
    category = Column(String, nullable=False)          # "Core", "Charging", "Policy", …
    category_abbrev = Column(String, nullable=False)   # "COR", "CHR", …
    instance_label = Column(String, nullable=False)    # e.g. "DEL-01"
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dra_type", "instance_label", name="uq_dra_instance"),
        Index("idx_dra_instance_lookup", "dra_type", "instance_label"),
        Index("idx_dra_site_category", "site", "category"),
        Index("idx_dra_active", "is_active"),
    )
