from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="IRIS_", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./iris.db"
    storage_backend: str = "local"
    storage_path: str = "./data"
    azure_storage_account_url: str | None = None
    azure_storage_container: str = "iris-images"
    auth_mode: str = "development"
    jwt_issuer: str | None = None
    jwt_audience: str = "iris-isolation-api"
    jwt_secret: str = Field(default="development-only-change-me", min_length=16)
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_file_bytes: int = 10 * 1024 * 1024
    serverless_max_file_bytes: int = 4 * 1024 * 1024
    max_batch_size: int = 10
    rate_limit_per_minute: int = 30
    unet_checkpoint: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()