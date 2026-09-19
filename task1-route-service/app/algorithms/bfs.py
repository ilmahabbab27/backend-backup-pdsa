"""Breadth-First Search (BFS) implementation for unweighted pathfinding / fewest-edge baseline."""

from collections import deque
import time
from typing import Optional

# T1DS: BFS algorithm for finding the route with the fewest hops in an unweighted graph.

from app.algorithms.graph import Graph
from app.algorithms.helpers import calculate_path_distance, reconstruct_path
from app.algorithms.types import AlgorithmResult


def bfs_search(
    graph: Graph, start: str, destination: str
) -> AlgorithmResult:
    """Find the route between start and destination using Breadth-First Search (BFS).

    BFS explores vertices in order of hop-distance (edge count) from the start node.
    It uses a FIFO queue, visiting every node at depth d before moving to depth d+1.

    IMPORTANT LIMITATION:
    BFS finds the route with the fewest road segments (hops/edges). In a weighted
    transportation network where road distances vary, the route with fewer edges
    is frequently NOT the shortest physical route. BFS serves as an unweighted
    baseline to highlight the necessity of weighted algorithms (Dijkstra and A*).

    Complexity:
        Time: O(V + E) where V is the number of cities and E is the number of roads.
        Space: O(V) for the queue, visited set, and parent mapping.
    """
    t0 = time.perf_counter()

    if not graph.has_node(start) or not graph.has_node(destination):
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return AlgorithmResult(
            algorithm="BFS",
            start=start,
            destination=destination,
            path=[],
            distance_km=0.0,
            nodes_explored=0,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=False,
            notes="Invalid start or destination node (not present in graph).",
        )

    if start == destination:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return AlgorithmResult(
            algorithm="BFS",
            start=start,
            destination=destination,
            path=[start],
            distance_km=0.0,
            nodes_explored=1,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=True,
            notes="Start and destination are identical.",
        )

    queue: deque[str] = deque([start])
    visited: set[str] = {start}
    parent: dict[str, Optional[str]] = {start: None}
    nodes_explored = 0
    found = False

    while queue:
        current = queue.popleft()
        nodes_explored += 1

        if current == destination:
            found = True
            break

        for neighbor, _ in graph.get_neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                parent[neighbor] = current
                queue.append(neighbor)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if not found or destination not in parent:
        return AlgorithmResult(
            algorithm="BFS",
            start=start,
            destination=destination,
            path=[],
            distance_km=0.0,
            nodes_explored=nodes_explored,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=False,
            notes="No route exists between the selected locations (unreachable / disconnected graph).",
        )

    path = reconstruct_path(parent, destination)
    dist = calculate_path_distance(graph, path)

    return AlgorithmResult(
        algorithm="BFS",
        start=start,
        destination=destination,
        path=path,
        distance_km=dist,
        nodes_explored=nodes_explored,
        execution_time_ms=round(elapsed_ms, 4),
        is_optimal_distance=False,
        notes="BFS minimizes edge hops (segments), which may not be the minimum physical distance on a weighted network.",
    )
