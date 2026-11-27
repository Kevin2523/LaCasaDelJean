"""Runtime settings for the private MCP inventory service."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    """Configuration loaded from environment variables (no DB credentials)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    api_internal_url: str = "http://api:8000"
    hermes_mcp_shared_secret: str = ""
    mcp_actor_assertion_secret: str = ""
    mcp_approval_signing_secret: str = ""
    mcp_actor_max_ttl_seconds: int = 60
    mcp_approval_max_ttl_seconds: int = 120
    mcp_port: int = 8010
    http_timeout_seconds: float = 15.0


@lru_cache(maxsize=1)
def get_mcp_settings() -> MCPSettings:
    """Return cached MCP settings."""
    return MCPSettings()
