"""HTTP endpoints for Task 3 network analysis."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.network_models import AvailableNodesResponse, NetworkAnalysisResponse
from app.repositories.network_repository import NetworkRepository, NetworkRepositoryError
from app.services.network_service import InvalidStartNodeError, NetworkAnalysisService


router = APIRouter(prefix="/api/network", tags=["network"])


def get_network_repository() -> NetworkRepository:
    """Create a repository per request; tests can override this dependency."""
    return NetworkRepository()


def get_network_service(
    repository: Annotated[NetworkRepository, Depends(get_network_repository)],
) -> NetworkAnalysisService:
    """Create the application service using the injected repository."""
    return NetworkAnalysisService(repository)


ServiceDependency = Annotated[NetworkAnalysisService, Depends(get_network_service)]


@router.get("/nodes", response_model=AvailableNodesResponse)
def list_nodes(service: ServiceDependency) -> AvailableNodesResponse:
    """Return all locations available as analysis starting nodes."""
    try:
        return service.list_nodes()
    except NetworkRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Network data is temporarily unavailable",
        ) from exc


@router.get("/analysis/{start_node}", response_model=NetworkAnalysisResponse)
def analyze_network(
    start_node: str,
    service: ServiceDependency,
) -> NetworkAnalysisResponse:
    """Run complete network analysis from a selected location."""
    try:
        return service.analyze(start_node)
    except InvalidStartNodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NetworkRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Network data is temporarily unavailable",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored network data is invalid",
        ) from exc
