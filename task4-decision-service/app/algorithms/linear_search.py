"""Linear-search baseline for Task 4 facility recommendation."""

from app.algorithms.common import Candidate


# T4DS: Baseline algorithm that ranks by shortest distance only, without capacity or availability checks.
def linear_search(candidates: list[Candidate]) -> list[Candidate]:
    """Pick the nearest facility using a single-criterion distance score."""
    for candidate in candidates:
        distance = candidate["distance_km"]
        candidate["score"] = 1.0 / (1.0 + distance)
    return candidates
