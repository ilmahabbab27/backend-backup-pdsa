"""Construct deterministic adjacency dictionaries from location and road data."""

from collections.abc import Iterable

from app.models.network_models import Location, Road


# T3DS: Adjacency map representing the city road network as a node-to-neighbour graph for traversal and analysis.
Adjacency = dict[str, list[str]]


# T3DS: Transform location and road records into a deterministic adjacency dictionary before BFS/DFS and centrality analysis.
def build_adjacency(
    locations: Iterable[Location],
    roads: Iterable[Road],
) -> Adjacency:
    """Build an adjacency dictionary and reject roads with unknown endpoints."""
    location_keys = {location.location_key for location in locations}
    neighbours: dict[str, set[str]] = {key: set() for key in location_keys}

    for road in roads:
        if road.from_location_key not in location_keys:
            raise ValueError(
                f"Road references unknown from-location {road.from_location_key!r}"
            )
        if road.to_location_key not in location_keys:
            raise ValueError(
                f"Road references unknown to-location {road.to_location_key!r}"
            )

        neighbours[road.from_location_key].add(road.to_location_key)
        if road.is_bidirectional:
            neighbours[road.to_location_key].add(road.from_location_key)

    return {
        node: sorted(neighbours[node])
        for node in sorted(neighbours)
    }
