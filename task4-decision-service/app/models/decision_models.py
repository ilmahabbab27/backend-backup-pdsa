"""Request and response models for the Public Facility Recommender.

The user asks: "Given my location and the type of facility I need, which
facility should I go to?" They can weight three criteria - distance,
capacity and availability - according to how much each matters to them.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Algorithm(str, Enum):
    """Which ranking technique to run.

    Task 4 compares three approaches:
      - linear_search: a simple baseline that scans and picks by a single rule.
      - weighted_ranking: normalise each criterion, apply user weights, sum.
      - heuristic_scoring: rule-of-thumb scoring with penalties/bonuses.
    """

    LINEAR_SEARCH = "linear_search"
    WEIGHTED_RANKING = "weighted_ranking"
    HEURISTIC_SCORING = "heuristic_scoring"


class CriteriaWeights(BaseModel):
    """How much each criterion matters (0..1 each). They need not sum to 1;
    the ranking algorithm normalises them internally."""

    distance: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Importance of being close (higher = distance matters more).",
    )
    capacity: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Importance of large total capacity.",
    )
    availability: float = Field(
        default=0.2, ge=0.0, le=1.0,
        description="Importance of having free space right now.",
    )


class RecommendationRequest(BaseModel):
    """Input to the recommender."""

    location_key: str = Field(
        ...,
        description="Where the user is, e.g. 'residential'. Must exist in locations.",
        examples=["residential"],
    )
    facility_type: str = Field(
        default="hospital",
        description="Type of facility needed, e.g. 'hospital'.",
        examples=["hospital"],
    )
    weights: CriteriaWeights = Field(default_factory=CriteriaWeights)
    algorithm: Algorithm = Field(
        default=Algorithm.WEIGHTED_RANKING,
        description="Which ranking technique to use.",
    )


class ScoredFacility(BaseModel):
    """A single facility with its computed metrics and final score."""

    location_key: str
    name: str
    facility_type: str
    distance_km: float = Field(description="Straight-line distance from the user.")
    capacity: Optional[int]
    current_load: int
    availability: int = Field(description="Free headroom = capacity - current_load.")
    score: float = Field(description="Final score; higher is better.")
    rank: int = Field(description="1 = best recommendation.")


class RecommendationResponse(BaseModel):
    """Output of the recommender."""

    algorithm: Algorithm
    location_key: str
    facility_type: str
    recommended: Optional[ScoredFacility] = Field(
        description="The top-ranked facility, or null if none found."
    )
    ranked: list[ScoredFacility] = Field(
        default_factory=list,
        description="All candidate facilities in ranked order (best first).",
    )
