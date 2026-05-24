import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://carbonverify:carbonverify_secret@localhost:5432/carbonverify"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MFA
    MFA_ISSUER_NAME: str = "CarbonVerify"
    MFA_REQUIRED_ROLES: str = "admin,operator"  # comma-separated

    # Session / Inactivity
    SESSION_INACTIVITY_TIMEOUT_MINUTES: int = 30

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "carbonverify-uploads"

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:5173"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Kimi API (Moonshot AI)
    KIMI_API_KEY: str = ""
    KIMI_API_BASE: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "moonshot-v1-8k"

    # Radix DLT
    RADIX_GATEWAY_URL: str = "https://mainnet.radixdlt.com"
    RADIX_NETWORK_ID: int = 1  # 1 = mainnet, 2 = stokenet
    RADIX_PRIVATE_KEY_HEX: str = ""  # For signing transactions
    RADIX_ACCOUNT_ADDRESS: str = ""
    RADIX_ENABLED: bool = False

    # Encryption
    ENCRYPTION_KEY_HEX: str = ""  # 32-byte hex for field-level encryption
    DATA_RETENTION_YEARS_RAW_PHOTOS: int = 7

    # Compliance
    BREACH_NOTIFICATION_SLA_HOURS: int = 72
    DSR_RESPONSE_SLA_DAYS: int = 30


@lru_cache()
def get_settings() -> Settings:
    return Settings()
