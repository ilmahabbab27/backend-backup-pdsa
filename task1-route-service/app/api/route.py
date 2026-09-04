"""FastAPI API endpoints for City Route Optimization (Task 1)."""

from fastapi import APIRouter, HTTPException, Query, status

from app.models.route_models import (
    BenchmarkResponse,
    CityModel,
    ComparisonRequest,
    ComparisonResponse,
    NetworkResponse,
    RouteRequest,
    RouteResponse,
)
from app.services.route_service import RouteOptimizationException, RouteService

router = APIRouter(prefix="/api/route", tags=["route"])
_service = RouteService()


@router.get(
    "/cities",
    response_model=list[CityModel],
    summary="Get all available cities in the transportation network.",
)
async def get_cities() -> list[CityModel]:
    """Return all city vertices available for route planning."""
    return _service.get_cities()


@router.get(
    "/network",
    response_model=NetworkResponse,
    summary="Get full network topology including cities and connecting roads.",
)
async def get_network() -> NetworkResponse:
    """Return complete graph vertices and edges."""
    return _service.get_network()


@router.post(
    "/plan",
    response_model=RouteResponse,
    summary="Calculate optimal route between start and destination using chosen algorithm.",
)
async def plan_route(request: RouteRequest) -> RouteResponse:
    """Find a route between two cities using BFS, Dijkstra, or A*."""
    try:
        return _service.find_route(request)
    except RouteOptimizationException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during route planning: {exc}",
        ) from exc


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    summary="Compare BFS, Dijkstra, and A* performance on the same journey.",
)
async def compare_routes(request: ComparisonRequest) -> ComparisonResponse:
    """Run all three algorithms on the exact same city pair and measure actual performance metrics."""
    try:
        return _service.compare_algorithms(request.start, request.destination)
    except RouteOptimizationException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during algorithm comparison: {exc}",
        ) from exc


@router.post(
    "/benchmark",
    response_model=BenchmarkResponse,
    summary="Run empirical benchmark experiments across graph sizes.",
)
async def benchmark_algorithms(
    iterations: int = Query(default=30, ge=1, le=200, description="Iterations to average")
) -> BenchmarkResponse:
    """Empirically evaluate BFS, Dijkstra, and A* across Small, Medium, and Large graph networks."""
    try:
        return _service.run_benchmarks(iterations=iterations)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during benchmark execution: {exc}",
        ) from exc
