"""API v1 router definitions for Waste Route Optimization Service."""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict
from fastapi import APIRouter, Depends, status

from app.api.deps import get_optimizer_service, get_supabase_map_repository
from app.models.schemas import (
    HealthResponse,
    OptimizationRequest,
    OptimizationResponse,
)
from app.services.optimizer_service import OptimizerService
from app.repositories.supabase_map_repository import SupabaseMapRepository

api_router = APIRouter()


@api_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """Return health status and current UTC ISO-8601 timestamp."""
    from app.utils.logger import log_info
    log_info("Health check ping received -> Service healthy (status: ok)")
    return HealthResponse(
        status="ok",
        service="task5-optimization-service",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@api_router.get(
    "/map",
    response_model=Dict[str, Any],
    summary="Get City Road Network Map",
    tags=["map"],
)
def get_city_map(
    repository: Annotated[SupabaseMapRepository, Depends(get_supabase_map_repository)],
) -> Dict[str, Any]:
    """Retrieve the frontend-ready enlarged 2D city map payload from Supabase."""
    return repository.get_enlarged_city_map()


@api_router.post(
    "/optimize",
    response_model=OptimizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize Waste Collection Routes",
    tags=["optimization"],
)
def optimize_routes(
    request: OptimizationRequest,
    service: Annotated[OptimizerService, Depends(get_optimizer_service)],
) -> OptimizationResponse:
    """Solve multi-truck allocation, capacity enforcement, and optimal sequence routing.

    - Computes all-pairs Dijkstra road distance matrices.
    - Dispatches trucks from Start Depot (D0) to visit assigned smart bins.
    - Routes trucks to Waste Disposal Facility (T1) and returns to Depot (D0).
    - Returns detailed route sequences, turn-by-turn coordinate paths, and performance metrics.
    """
    return service.optimize_waste_collection(request)
