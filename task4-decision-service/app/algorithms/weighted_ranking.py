"""Weighted multi-criteria ranking for Task 4 recommendations."""

from app.algorithms.common import Candidate, _normalise_min_max


# T4DS: Apply weighted, normalised scores across distance, capacity, and availability.
def weighted_ranking(
    candidates: list[Candidate], weights: dict[str, float]
) -> list[Candidate]:
    """Normalise each criterion and combine them using the supplied user weights."""
    if not candidates:
        return candidates

    # T4DS: Collect each criterion so the main scoring model can normalise the whole candidate set consistently.
    distances = [candidate["distance_km"] for candidate in candidates]
    capacities = [float(candidate["capacity"] or 0) for candidate in candidates]
    availabilities = [float(candidate["availability"]) for candidate in candidates]

    # T4DS: Convert distance to a "lower is better" score while capacity and availability are treated as benefit criteria.
    norm_dist = _normalise_min_max(distances, higher_is_better=False)
    norm_cap = _normalise_min_max(capacities, higher_is_better=True)
    norm_avail = _normalise_min_max(availabilities, higher_is_better=True)

    # T4DS: Normalise user preferences so the weighted sum remains proportionally meaningful.
    total_weight = (
        weights["distance"] + weights["capacity"] + weights["availability"]
    )
    if total_weight == 0:
        weight_distance = weight_capacity = weight_availability = 1 / 3
    else:
        weight_distance = weights["distance"] / total_weight
        weight_capacity = weights["capacity"] / total_weight
        weight_availability = weights["availability"] / total_weight

    # T4DS: Combine the three weighted factors into the final score for each facility candidate.
    for index, candidate in enumerate(candidates):
        candidate["score"] = (
            weight_distance * norm_dist[index]
            + weight_capacity * norm_cap[index]
            + weight_availability * norm_avail[index]
        )
    return candidates
