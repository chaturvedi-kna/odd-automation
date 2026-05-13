import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class PrrDumpRow(Base):
    __tablename__ = "prr_dump_rows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    snapshot_id = Column(
        String,
        ForeignKey("dump_snapshots.id"),
        nullable=False,
    )

    name = Column(String, nullable=False)
    realm = Column(String, nullable=True)
    route_list_name = Column(String, nullable=True)
    peer_route_table = Column(String, nullable=True)

    raw_payload = Column(JSONB, nullable=True)