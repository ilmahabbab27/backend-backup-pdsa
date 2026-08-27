"""Application configuration for the Intelligent Decision Service.

Reads values from environment variables (loaded from a local .env file).
Never commit the real .env — only .env.example is pushed.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from the environment."""

    APP_NAME: str = "Intelligent Decision Service"
    APP_PORT: int = 8004

    # Supabase connection. These MUST be provided in .env for the
    # repository layer to reach the database.
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read the environment only once)."""
    return Settings()
