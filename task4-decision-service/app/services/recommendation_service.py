"""Application logic for the Public Facility Recommender.

The service ties the pieces together:
  request -> fetch user location + candidate facilities (repository)
          -> compute distance for each candidate (haversine)
          -> run the chosen ranking algorithm (algorithms)
          -> sort, rank and return a response model.

No database code and no raw algorithm maths live here - only orchestration.
"""
from app.algorithms import ranking
from app.models.decision_models import (
    Algorithm,
    RecommendationRequest,
    RecommendationResponse,
    ScoredFacility,
)
from app.repositories.facility_repository import FacilityRepository
from app.utils.geo import haversine_km


class LocationNotFoundError(Exception):
    """Raised when the requested user location_key does not exist."""


class RecommendationService:
    """Coordinates facility recommendation for a user request."""

    def __init__(self, repository: FacilityRepository | None = None) -> None:
        self.repository = repository or FacilityRepository()

    def recommend(
        self, request: RecommendationRequest
    ) -> RecommendationResponse:
        """Produce a ranked facility recommendation for the given request."""
        origin = self.repository.get_location(request.location_key)
        if origin is None:
            raise LocationNotFoundError(
                f"Unknown location_key: {request.location_key!r}"
            )

        facilities = self.repository.get_facilities_by_type(
            request.facility_type
        )

        candidates = self._build_candidates(origin, facilities)

        # If we found nothing, return an empty (but valid) response.
        if not candidates:
            return RecommendationResponse(
                algorithm=request.algorithm,
                location_key=request.location_key,
                facility_type=request.facility_type,
                recommended=None,
                ranked=[],
            )

        scored = self._run_algorithm(request, candidates)

        # Highest score first; ties broken by shorter distance.
        scored.sort(key=lambda c: (-c["score"], c["distance_km"]))

        ranked = [
            self._to_scored_facility(c, rank=i + 1)
            for i, c in enumerate(scored)
        ]

        return RecommendationResponse(
            algorithm=request.algorithm,
            location_key=request.location_key,
            facility_type=request.facility_type,
            recommended=ranked[0],
            ranked=ranked,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_candidates(
        self, origin: dict, facilities: list[dict]
    ) -> list[dict]:
        """Attach distance and availability to each facility.

        Facilities missing coordinates are skipped (we cannot rank them by
        distance). availability = capacity - current_load, floored at 0.
        """
        candidates: list[dict] = []
        for fac in facilities:
            lat, lon = fac.get("latitude"), fac.get("longitude")
            if lat is None or lon is None:
                continue

            distance = haversine_km(
                origin["latitude"], origin["longitude"], lat, lon
            )
            capacity = fac.get("capacity")
            current_load = fac.get("current_load", 0) or 0
            availability = max((capacity or 0) - current_load, 0)

            candidates.append(
                {
                    "location_key": fac["location_key"],
                    "name": fac["name"],
                    "facility_type": fac["facility_type"],
                    "distance_km": round(distance, 4),
                    "capacity": capacity,
                    "current_load": current_load,
                    "availability": availability,
                }
            )
        return candidates

    def _run_algorithm(
        self, request: RecommendationRequest, candidates: list[dict]
    ) -> list[dict]:
        """Dispatch to the requested ranking algorithm."""
        if request.algorithm is Algorithm.LINEAR_SEARCH:
            return ranking.linear_search(candidates)
        if request.algorithm is Algorithm.HEURISTIC_SCORING:
            return ranking.heuristic_scoring(candidates)
        # Default / explicit weighted ranking.
        return ranking.weighted_ranking(
            candidates,
            {
                "distance": request.weights.distance,
                "capacity": request.weights.capacity,
                "availability": request.weights.availability,
            },
        )

    @staticmethod
    def _to_scored_facility(candidate: dict, rank: int) -> ScoredFacility:
        """Convert an internal candidate dict into the response model."""
        return ScoredFacility(
            location_key=candidate["location_key"],
            name=candidate["name"],
            facility_type=candidate["facility_type"],
            distance_km=candidate["distance_km"],
            capacity=candidate["capacity"],
            current_load=candidate["current_load"],
            availability=candidate["availability"],
            score=round(candidate["score"], 4),
            rank=rank,
        )
