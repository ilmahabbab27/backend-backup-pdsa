"""Geographic helpers.

Task 4 needs a distance between the user's location and each candidate
facility, but the facilities table stores no distance. Every location has
latitude/longitude, so we use the haversine formula for straight-line
("as the crow flies") distance in kilometres.

Note for the report: this is a simplification. A production system would
call the Task 1 routing service (Dijkstra/A*) for true road distance. Using
haversine keeps Task 4 self-contained and focused on *ranking*, which is its
actual assignment.
"""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return the great-circle distance in km between two lat/long points.

    Args:
        lat1, lon1: first point's latitude and longitude in degrees.
        lat2, lon2: second point's latitude and longitude in degrees.

    Returns:
        Distance in kilometres (float, >= 0).
    """
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    d_lat = lat2_r - lat1_r
    d_lon = lon2_r - lon1_r
    a = sin(d_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
