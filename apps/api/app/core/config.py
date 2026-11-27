"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for apps/api."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://lacasadeljean:lacasadeljean@localhost:5432/lacasadeljean_v2"
    media_root: str = "storage/media"
    cors_origins: str = "http://127.0.0.1:4200,http://localhost:4200"
    jwt_secret_key: str = "dev-only-insecure-jwt-secret-change-me-before-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60

    @property
    def cors_origins_list(self) -> list[str]:
        """Return parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
