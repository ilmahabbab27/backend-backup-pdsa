"""Task 4 facility-ranking algorithms package."""

# T4DS: Export the separate algorithm modules so callers can import either the package or the individual strategies.
from app.algorithms.common import _normalise_min_max
from app.algorithms.heuristic_scoring import heuristic_scoring
from app.algorithms.linear_search import linear_search
from app.algorithms.weighted_ranking import weighted_ranking

__all__ = [
    "_normalise_min_max",
    "linear_search",
    "weighted_ranking",
    "heuristic_scoring",
]
