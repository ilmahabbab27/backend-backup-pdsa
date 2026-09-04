"""Geographic distance calculations for route optimization."""

import math


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate great-circle distance between two points on Earth in kilometers.

    Uses the Haversine formula. The result is an admissible heuristic for A*
    because the straight-line (great circle) distance is always <= road distance.
    """
    if (lat1, lon1) == (lat2, lon2):
        return 0.0

    r = 6371.0  # Earth radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def euclidean_distance(
    x1: float, y1: float, x2: float, y2: float, scale_factor: float = 1.0
) -> float:
    """Calculate scaled Euclidean distance between two 2D points."""
    return math.hypot(x2 - x1, y2 - y1) * scale_factor
