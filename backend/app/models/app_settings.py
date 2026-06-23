from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.models.base import Base


class AppSettings(Base):
    """
    Singleton settings row (id=1).
    Administrators can update these via the /settings API.
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)  # always 1

    download_base_name = Column(String, nullable=True, default="ODD")
    download_version = Column(String, nullable=True, default="1.0")
    recon_cron_time = Column(String, nullable=True, default="02:00")
    dump_ingest_times = Column(String, nullable=True, default="06:00,18:00")

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
