"""Ranking algorithms for the Public Facility Recommender (Task 4).

Three techniques are implemented so they can be compared in the coursework
report on correctness, simplicity and behaviour:

  1. linear_search     - baseline: single-criterion scan (nearest facility).
  2. weighted_ranking  - normalise each criterion to 0..1, apply user weights.
  3. heuristic_scoring - rule-of-thumb scoring with bonuses and penalties.

Each function takes a list of "candidate" dicts. A candidate has:
    location_key, name, facility_type, distance_km, capacity,
    current_load, availability
and each returns the same list annotated with a float "score" (higher is
better) so the service can sort and rank uniformly.
"""
from typing import Any

Candidate = dict[str, Any]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalise_min_max(
    values: list[float], *, higher_is_better: bool
) -> list[float]:
    """Scale a list of numbers to the 0..1 range.

    If higher_is_better is False (e.g. distance), the scale is inverted so
    that the smallest raw value gets the best (1.0) normalised score.
    When all values are equal, every item scores 1.0 (the criterion cannot
    differentiate them).
    """
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [1.0 for _ in values]
    if higher_is_better:
        return [(v - lo) / span for v in values]
    return [(hi - v) / span for v in values]


# --------------------------------------------------------------------------- #
# 1. Linear search (baseline)
# --------------------------------------------------------------------------- #
def linear_search(candidates: list[Candidate]) -> list[Candidate]:
    """Baseline technique: pick by a single criterion (shortest distance).

    This ignores capacity and availability entirely. It exists to show, in
    the report, how a naive one-factor search compares to true multi-criteria
    ranking. Score = inverse of distance so nearer facilities score higher.
    """
    for c in candidates:
        dist = c["distance_km"]
        # +1 avoids division by zero and keeps scores finite and comparable.
        c["score"] = 1.0 / (1.0 + dist)
    return candidates


# --------------------------------------------------------------------------- #
# 2. Weighted ranking (the main technique)
# --------------------------------------------------------------------------- #
def weighted_ranking(
    candidates: list[Candidate], weights: dict[str, float]
) -> list[Candidate]:
    """Multi-criteria weighted ranking.

    Steps:
      1. Normalise each criterion across all candidates to 0..1
         (distance inverted: closer is better).
      2. Normalise the user's weights so they sum to 1.
      3. score = w_d * norm_distance + w_c * norm_capacity
                 + w_a * norm_availability.

    Args:
        candidates: candidate facilities (mutated in place with "score").
        weights: dict with keys distance, capacity, availability.
    """
    if not candidates:
        return candidates

    distances = [c["distance_km"] for c in candidates]
    capacities = [float(c["capacity"] or 0) for c in candidates]
    availabilities = [float(c["availability"]) for c in candidates]

    norm_dist = _normalise_min_max(distances, higher_is_better=False)
    norm_cap = _normalise_min_max(capacities, higher_is_better=True)
    norm_avail = _normalise_min_max(availabilities, higher_is_better=True)

    w_total = weights["distance"] + weights["capacity"] + weights["availability"]
    if w_total == 0:
        # Degenerate input: treat all criteria as equally important.
        w_d = w_c = w_a = 1 / 3
    else:
        w_d = weights["distance"] / w_total
        w_c = weights["capacity"] / w_total
        w_a = weights["availability"] / w_total

    for i, c in enumerate(candidates):
        c["score"] = (
            w_d * norm_dist[i]
            + w_c * norm_cap[i]
            + w_a * norm_avail[i]
        )
    return candidates


# --------------------------------------------------------------------------- #
# 3. Heuristic scoring
# --------------------------------------------------------------------------- #
def heuristic_scoring(candidates: list[Candidate]) -> list[Candidate]:
    """Rule-of-thumb scoring with fixed bonuses and penalties.

    Unlike weighted ranking, this uses hand-tuned rules rather than
    user weights - useful to contrast a "human expert rules" style
    approach with a formal normalised model. Rules:

      * Start every facility at a base score of 100.
      * Subtract 8 points per kilometre of distance (closer is better).
      * Add 0.1 points per unit of free availability (headroom helps).
      * Add a 15-point bonus if the facility still has >25% capacity free.
      * Apply a 30-point penalty if the facility is effectively full
        (availability <= 0).

    Unlike the other two techniques this score is not bounded to 0..1 - it
    is a raw rule-based point total, intentionally left unnormalised so the
    report can contrast it against the normalised techniques. Callers that
    display it alongside linear_search/weighted_ranking should label it as
    a raw score rather than a percentage.
    """
    for c in candidates:
        capacity = c["capacity"] or 0
        availability = c["availability"]

        score = 100.0
        score -= 8.0 * c["distance_km"]
        score += 0.1 * availability

        if capacity > 0 and availability / capacity > 0.25:
            score += 15.0
        if availability <= 0:
            score -= 30.0

        c["score"] = score
    return candidates
