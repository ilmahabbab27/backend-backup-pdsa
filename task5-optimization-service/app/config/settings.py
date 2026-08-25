"""Application configuration and environment settings."""

from functools import lru_cache
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the optimization service."""

    APP_NAME: str = "Waste Route Optimization Service"
    APP_PORT: int = 8005
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = ["*"]
    MAP_DATA_PATH: str = "data/city_map.json"

    # Base directory of task5-optimization-service
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Normalize CORS origins from JSON list or comma-separated string."""
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @property
    def resolved_map_data_path(self) -> Path:
        """Return the absolute path to city_map.json."""
        path = Path(self.MAP_DATA_PATH)
        if not path.is_absolute():
            return (self.BASE_DIR / path).resolve()
        return path.resolve()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
