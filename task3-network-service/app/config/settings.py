"""Environment-based configuration for the Network Analysis Service."""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


SERVICE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=SERVICE_ROOT / ".env", override=False)


DEFAULT_ALLOWED_ORIGINS = ("http://localhost:5173",)


def _parse_origins(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated origin list, excluding blank entries."""
    if value is None:
        return DEFAULT_ALLOWED_ORIGINS

    origins = tuple(origin.strip() for origin in value.split(",") if origin.strip())
    return origins or DEFAULT_ALLOWED_ORIGINS


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    app_name: str = "Network Analysis Service"
    app_port: int = 8003
    supabase_url: str | None = None
    supabase_key: str | None = None
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the current process environment."""
        raw_port = os.getenv("APP_PORT", "8003")
        try:
            app_port = int(raw_port)
        except ValueError as exc:
            raise ValueError("APP_PORT must be an integer") from exc

        return cls(
            app_name=os.getenv("APP_NAME", "Network Analysis Service"),
            app_port=app_port,
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
            allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance for application use."""
    return Settings.from_env()
