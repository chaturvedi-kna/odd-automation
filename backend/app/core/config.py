from pydantic import Field
from pydantic_settings import BaseSettings  # pydantic v2; use `from pydantic import BaseSettings` for v1


class Settings(BaseSettings):
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    DATABASE_URL: str
    DATABASE_SYNC_URL: str

    REDIS_URL: str

    PRR_NAME_MAX_LEN: int = Field(default=16, validation_alias="PRR_NAME_MAX_LEN")
    PRR_SCOPE_SUFFIXES: str = Field(default="s6a,s6d")
    RBAR_SCOPE_SUFFIXES: str = Field(default="vdea,vpcrf")

    # FIX: was declared twice (duplicate EXPORT_PATH)
    EXPORT_PATH: str = "/app/exports"
    DUMP_INCOMING_PATH: str = "/app/dumps/incoming"
    DUMP_PROCESSED_PATH: str = "/app/dumps/processed"

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    RECON_CRON_TIME: str = "02:00"
    DUMP_INGEST_TIMES: str = "06:00,18:00"

    CORS_ORIGINS: str = "http://localhost"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
