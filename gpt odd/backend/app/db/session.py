from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Async engine (FastAPI)
async_engine = create_async_engine(settings.DATABASE_URL,future=True,pool_pre_ping=True,pool_recycle=3600,)
AsyncSessionLocal = async_sessionmaker(
    async_engine, expire_on_commit=False
)

# Sync engine (Celery)
sync_engine = create_engine(settings.DATABASE_SYNC_URL,pool_pre_ping=True,pool_recycle=3600,)
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)