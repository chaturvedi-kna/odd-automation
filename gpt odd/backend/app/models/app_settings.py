from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.models.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)

    download_base_name = Column(String, nullable=False, default="ODD_ILD")
    download_version = Column(Integer, nullable=False, default=1)

    recon_cron_time = Column(String, nullable=True)
    dump_ingest_times = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )