"""Helper functions for path reconstruction and path metric calculations."""

from typing import Optional
from app.algorithms.graph import Graph


def reconstruct_path(
    parent: dict[str, Optional[str]], destination: str
) -> list[str]:
    """Reconstruct path from start to destination using the parent map."""
    if destination not in parent:
        return []

    path: list[str] = []
    current: Optional[str] = destination
    while current is not None:
        path.append(current)
        current = parent.get(current)
    path.reverse()
    return path


def calculate_path_distance(graph: Graph, path: list[str]) -> float:
    """Sum the road distances along a path in the graph."""
    if len(path) <= 1:
        return 0.0

    total_km = 0.0
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        # Find weight from u to v
        found = False
        min_weight = float("inf")
        for neighbor, weight in graph.get_neighbors(u):
            if neighbor == v and weight < min_weight:
                min_weight = weight
                found = True
        if found:
            total_km += min_weight
    return round(total_km, 2)
