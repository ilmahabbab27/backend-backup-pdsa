"""FastAPI dependencies for dependency injection."""

from functools import lru_cache
from typing import Annotated
from fastapi import Depends

from app.config.settings import Settings, get_settings
from app.repositories.map_repository import MapRepository
from app.repositories.supabase_map_repository import SupabaseMapRepository
from app.services.optimizer_service import OptimizerService


@lru_cache()
def get_map_repository() -> MapRepository:
    """Return a singleton instance of MapRepository."""
    settings = get_settings()
    return MapRepository(settings=settings)


def get_optimizer_service(
    map_repo: Annotated[MapRepository, Depends(get_map_repository)],
) -> OptimizerService:
    """Dependency provider for OptimizerService."""
    return OptimizerService(map_repo=map_repo)


def get_supabase_map_repository(
    map_repo: Annotated[MapRepository, Depends(get_map_repository)],
) -> SupabaseMapRepository:
    """Return the repository used by the public 2D map endpoint."""
    return SupabaseMapRepository(settings=get_settings(), map_repo=map_repo)
