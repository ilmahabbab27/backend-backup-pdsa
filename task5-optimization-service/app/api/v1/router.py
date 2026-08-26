"""API v1 router definitions for Waste Route Optimization Service."""

from datetime import datetime, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_optimizer_service
from app.models.schemas import (
    CityMapResponse,
    FleetEstimateResponse,
    HealthResponse,
    NodeSchema,
    OptimizationRequest,
    OptimizationResponse,
)
from app.services.optimizer_service import OptimizerService

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
    response_model=CityMapResponse,
    summary="Get City Road Network Map",
    tags=["map"],
)
def get_city_map(
    service: Annotated[OptimizerService, Depends(get_optimizer_service)],
) -> CityMapResponse:
    """Retrieve full city map nodes, coordinates, bin weights, and road network topology."""
    return service.get_city_map()


@api_router.get(
    "/nodes",
    response_model=List[NodeSchema],
    summary="Get Road Network Nodes",
    tags=["map"],
)
def get_nodes(
    service: Annotated[OptimizerService, Depends(get_optimizer_service)],
    node_type: Optional[str] = Query(
        None,
        alias="type",
        description="Filter nodes by type ('start', 'destination', 'intersection', 'bin')",
    ),
) -> List[NodeSchema]:
    """Retrieve all road network nodes, optionally filtered by node type."""
    return service.get_nodes(node_type)


@api_router.get(
    "/bins",
    response_model=List[NodeSchema],
    summary="Get Smart Waste Bins",
    tags=["bins"],
)
def get_bins(
    service: Annotated[OptimizerService, Depends(get_optimizer_service)],
) -> List[NodeSchema]:
    """Retrieve all active smart waste bins with their location coordinates and waste weights."""
    return service.get_bins()


@api_router.get(
    "/depots",
    response_model=List[NodeSchema],
    summary="Get Facility Depots and Disposal Sites",
    tags=["facilities"],
)
def get_depots(
    service: Annotated[OptimizerService, Depends(get_optimizer_service)],
) -> List[NodeSchema]:
    """Retrieve the central start depot (D0) and waste disposal / treatment facility (T1)."""
    return service.get_depots()


@api_router.get(
    "/fleet/estimate",
    response_model=FleetEstimateResponse,
    summary="Estimate Fleet Requirements",
    tags=["fleet"],
)
def get_fleet_estimate(
    service: Annotated[OptimizerService, Depends(get_optimizer_service)],
    truck_capacity_kg: int = Query(
        1500,
        ge=100,
        description="Uniform capacity per truck in kilograms",
    ),
) -> FleetEstimateResponse:
    """Calculate the theoretical minimum fleet size required to collect all city waste."""
    return service.get_fleet_estimate(truck_capacity_kg=truck_capacity_kg)


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

