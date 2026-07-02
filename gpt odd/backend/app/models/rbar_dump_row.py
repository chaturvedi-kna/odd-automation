import uuid
from sqlalchemy import Column, String, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class RbarDumpRow(Base):
    __tablename__ = "rbar_dump_rows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    snapshot_id = Column(
        String,
        ForeignKey("dump_snapshots.id"),
        nullable=False,
    )

    table_name = Column(String, nullable=True)
    start_addr = Column(BigInteger, nullable=True)
    end_addr = Column(BigInteger, nullable=True)
    destination = Column(String, nullable=True)

    raw_payload = Column(JSONB, nullable=True)