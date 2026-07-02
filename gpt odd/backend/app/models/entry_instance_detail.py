import uuid
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class EntryInstanceDetail(Base):
    __tablename__ = "entry_instance_details"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    instance_status_id = Column(
        String,
        ForeignKey("entry_instance_statuses.id"),
        nullable=False,
    )

    entry_id = Column(String, nullable=False)
    entry_type = Column(String, nullable=False)

    dra_type = Column(String, nullable=False)
    instance_label = Column(String, nullable=False)

    final_prt_rule = Column(String, nullable=True)
    realm = Column(String, nullable=True)

    start_addr = Column(BigInteger, nullable=True)
    end_addr = Column(BigInteger, nullable=True)
    destination = Column(String, nullable=True)

    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "instance_status_id",
            name="uq_entry_instance_detail_status"
        ),
    )