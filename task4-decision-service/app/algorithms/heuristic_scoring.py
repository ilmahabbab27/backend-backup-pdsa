"""Heuristic score model for Task 4 facility recommendation."""

from app.algorithms.common import Candidate


# T4DS: Rule-based scoring adds bonuses for spare capacity and penalties for long distance or full facilities.
def heuristic_scoring(candidates: list[Candidate]) -> list[Candidate]:
    """Use human-readable rules to score facilities instead of normalised weighting."""
    # T4DS: Use a simple expert-rule score: start near 100, penalise distance, reward spare capacity, and downgrade full facilities.
    for candidate in candidates:
        capacity = candidate["capacity"] or 0
        availability = candidate["availability"]

        score = 100.0
        score -= 8.0 * candidate["distance_km"]
        score += 0.1 * availability

        if capacity > 0 and availability / capacity > 0.25:
            score += 15.0
        if availability <= 0:
            score -= 30.0

        candidate["score"] = score
    return candidates
