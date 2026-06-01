from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Database
    DATABASE_URL: str
    DATABASE_READ_REPLICA_URL: str = ""  # Optional read replica

    # Redis
    REDIS_URL: str

    # JWT
    SECRET_KEY: str = Field(min_length=32)
    SECRET_KEY_PREVIOUS: str = ""  # For zero-downtime rotation
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MFA
    MFA_ISSUER_NAME: str = "CarbonVerify"
    MFA_REQUIRED_ROLES: str = "admin,operator"  # comma-separated

    # Session / Inactivity
    SESSION_INACTIVITY_TIMEOUT_MINUTES: int = 30

    # AWS S3 — no default; must be explicitly configured
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""

    # App
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = ""

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

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

    # ClamAV
    CLAMAV_SOCKET_PATH: str = ""  # e.g., /tmp/clamd.socket
    CLAMAV_HOST: str = ""  # e.g., clamav
    CLAMAV_PORT: int = 3310

    # Compliance
    BREACH_NOTIFICATION_SLA_HOURS: int = 72
    DSR_RESPONSE_SLA_DAYS: int = 30

    # IoT Webhook
    IOT_WEBHOOK_API_KEY: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""

    # Lead Intelligence Engine
    LEAD_SCRAPER_MODE: str = "demo"  # "demo" or "live"
    LEAD_SCRAPER_RATE_LIMIT_RPS: float = 0.5  # requests per second
    LEAD_SCRAPER_REQUEST_TIMEOUT: int = 30
    LEAD_SCRAPER_MAX_RETRIES: int = 3
    LEAD_SCRAPER_RETRY_DELAY: int = 5

    # Kenya National Carbon Registry
    KENYA_NATIONAL_REGISTRY_BASE_URL: str = ""  # e.g. https://api.kenyacarbonregistry.go.ke/v1
    KENYA_NATIONAL_REGISTRY_API_KEY: str = ""
    PROXY_URL: str = ""  # HTTP proxy for scraper (e.g., http://proxy:8080)
    SCRAPER_FORCE_HEADLESS: bool = False  # Force headless mode in production
    # Comma-separated list of user agents for rotation; falls back to default if empty
    SCRAPER_USER_AGENTS: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
