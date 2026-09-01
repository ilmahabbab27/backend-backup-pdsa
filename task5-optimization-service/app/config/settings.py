"""Application configuration and environment settings."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Configuration settings for the optimization service."""

    APP_NAME: str = "Waste Route Optimization Service"
    APP_PORT: int = 8005
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = ["*"]
    MAP_DATA_PATH: str = "data/city_map_tier3_dense.json"
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_MAP_TIER: str = "tier3_dense"
    USE_SUPABASE_MAP: bool = True
    STATIC_BIN_CAPACITY_KG: int = 400

    # Base directory of task5-optimization-service
    BASE_DIR: Path = SERVICE_DIR

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

    @classmethod
    def resolve_tier_id_from_path(cls, path_or_tier: Optional[str]) -> str:
        """Resolve a standard tier_id ('tier1_sparse', 'tier2_medium', 'tier3_dense') from string or path."""
        if not path_or_tier:
            return "tier3_dense"
        lower = path_or_tier.lower()
        if "tier1" in lower or "sparse" in lower:
            return "tier1_sparse"
        elif "tier2" in lower or "medium" in lower:
            return "tier2_medium"
        elif "tier3" in lower or "dense" in lower:
            return "tier3_dense"
        return path_or_tier

    @property
    def resolved_map_data_path(self) -> Path:
        """Return the absolute path to configured map JSON dataset."""
        path = Path(self.MAP_DATA_PATH)
        if not path.is_absolute():
            return (self.BASE_DIR / path).resolve()
        return path.resolve()

    model_config = SettingsConfigDict(
        env_file=(SERVICE_DIR / ".env.example", SERVICE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
