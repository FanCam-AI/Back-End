from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    # Apple OAuth
    APPLE_CLIENT_ID: str
    APPLE_TEAM_ID: str
    APPLE_KEY_ID: str
    APPLE_PRIVATE_KEY: str
    APPLE_JWKS_URL: str
    APPLE_REDIRECT_URI: str
    APPLE_ISS: str = "https://appleid.apple.com"

    # Token / Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SECRET_KEY: str
    ALGORITHM: str
    APP_CALLBACK_SCHEME: str

    # R2 (Cloudflare R2)
    R2_ENDPOINT: str
    R2_ACCESS_KEY: str
    R2_SECRET_KEY: str
    R2_BUCKET: str

    # Redis
    REDIS_CLOUD_HOST: str
    REDIS_CLOUD_PASSWORD: str
    APP_VERSION: str
    POSTGRESQL_DATABASE_URL: str

    FERNET_KEY: str
    RUNPOD_API_KEY: str
    RUNPOD_URL: str
    CLOUD_RUN_URL: str
    PROTECTION_PASSWORD: str
    CPU_LOAD_BALANCER_SERVERLESS_URL: str
    GPU_LOAD_BALANCER_SERVERLESS_URL: str
    CPU_QUEUE_SERVERLESS_URL: str
    GPU_QUEUE_SERVERLESS_URL: str
    REVENUECAT_WEBHOOK_SECRET: str

    # pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()