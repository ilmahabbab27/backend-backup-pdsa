"""Common helpers for Task 4 facility-ranking algorithms."""

from typing import Any

# T4DS: Candidate record describing a facility and the values used by the ranking logic.
Candidate = dict[str, Any]


# T4DS: Normalise a numeric list to the 0..1 range for multi-criteria weighting.
def _normalise_min_max(
    values: list[float], *, higher_is_better: bool
) -> list[float]:
    """Scale a list of numbers to the 0..1 range."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [1.0 for _ in values]
    if higher_is_better:
        return [(v - lo) / span for v in values]
    return [(hi - v) / span for v in values]
