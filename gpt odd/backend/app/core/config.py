from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    DATABASE_URL: str
    DATABASE_SYNC_URL: str

    REDIS_URL: str

    PRR_NAME_MAX_LEN: int = Field(..., env="PRR_NAME_MAX_LEN")
    PRR_SCOPE_SUFFIXES: str = Field(..., env="PRR_SCOPE_SUFFIXES")
    RBAR_SCOPE_SUFFIXES: str = Field(..., env="RBAR_SCOPE_SUFFIXES")

    EXPORT_PATH: str

    DUMP_INCOMING_PATH: str
    DUMP_PROCESSED_PATH: str
    
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    RECON_CRON_TIME: str
    DUMP_INGEST_TIMES: str
    
    EXPORT_PATH: str
    CORS_ORIGINS: str

    class Config:
        env_file = ".env"


settings = Settings()