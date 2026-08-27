"""API endpoints for the Public Facility Recommender (Task 4)."""
from fastapi import APIRouter, HTTPException, status

from app.models.decision_models import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendation_service import (
    LocationNotFoundError,
    RecommendationService,
)

router = APIRouter(prefix="/api/decision", tags=["decision"])

_service = RecommendationService()


@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    summary="Recommend the most suitable facility for a user.",
)
async def recommend_facility(
    request: RecommendationRequest,
) -> RecommendationResponse:
    """Rank facilities of the requested type for the user's location.

    Body example:
        {
          "location_key": "residential",
          "facility_type": "hospital",
          "weights": {"distance": 0.6, "capacity": 0.2, "availability": 0.2},
          "algorithm": "weighted_ranking"
        }
    """
    try:
        return _service.recommend(request)
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
