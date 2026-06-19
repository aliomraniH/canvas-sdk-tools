"""Configuration via pydantic-settings (same clean pattern as the memory server).

Deliberately contains NO Canvas credentials, NO database URL, and NO embedding
keys: this service is static, offline, and stateless.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Bearer token required on /mcp.  Distinct from the memory server's token.
    mcp_auth_token: str = "change-me"

    # Network binding.
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging.
    log_level: str = "INFO"

    # Default reference bucket used when a tool call omits sdk_version.
    default_sdk_version: str = "0.169.x"


def get_settings() -> Settings:
    """Return a fresh Settings instance (cheap; no global mutable state)."""
    return Settings()
