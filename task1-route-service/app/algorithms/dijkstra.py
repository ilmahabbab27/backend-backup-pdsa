"""Dijkstra's Algorithm for optimal shortest-path finding on weighted graphs."""

import heapq
import time
from typing import Optional

from app.algorithms.graph import Graph
from app.algorithms.helpers import calculate_path_distance, reconstruct_path
from app.algorithms.types import AlgorithmResult


def dijkstra_search(
    graph: Graph, start: str, destination: str
) -> AlgorithmResult:
    """Find the shortest physical distance route using Dijkstra's algorithm.

    Dijkstra's algorithm guarantees the globally optimal (minimum distance)
    path in graphs with non-negative edge weights. It uses a priority queue
    (binary min-heap) to greedily expand the vertex with the smallest tentative distance.

    Complexity:
        Time: O((V + E) log V) with adjacency list and binary min-heap.
        Space: O(V) for the distance map, settled set, priority queue, and parent map.
    """
    t0 = time.perf_counter()

    if not graph.has_node(start) or not graph.has_node(destination):
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return AlgorithmResult(
            algorithm="Dijkstra",
            start=start,
            destination=destination,
            path=[],
            distance_km=0.0,
            nodes_explored=0,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=True,
            notes="Invalid start or destination node (not present in graph).",
        )

    if start == destination:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return AlgorithmResult(
            algorithm="Dijkstra",
            start=start,
            destination=destination,
            path=[start],
            distance_km=0.0,
            nodes_explored=1,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=True,
            notes="Start and destination are identical.",
        )

    # Priority queue storing tuples of (accumulated_distance, node_id)
    pq: list[tuple[float, str]] = [(0.0, start)]
    distances: dict[str, float] = {start: 0.0}
    parent: dict[str, Optional[str]] = {start: None}
    settled: set[str] = set()
    nodes_explored = 0
    found = False

    while pq:
        current_dist, current_node = heapq.heappop(pq)

        # Skip if we already found a shorter path to this node
        if current_node in settled:
            continue

        settled.add(current_node)
        nodes_explored += 1

        if current_node == destination:
            found = True
            break

        for neighbor, weight in graph.get_neighbors(current_node):
            if neighbor in settled:
                continue

            tentative_dist = current_dist + weight
            if tentative_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = tentative_dist
                parent[neighbor] = current_node
                heapq.heappush(pq, (tentative_dist, neighbor))

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if not found or destination not in parent:
        return AlgorithmResult(
            algorithm="Dijkstra",
            start=start,
            destination=destination,
            path=[],
            distance_km=0.0,
            nodes_explored=nodes_explored,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=True,
            notes="No route exists between the selected locations (unreachable / disconnected graph).",
        )

    path = reconstruct_path(parent, destination)
    dist = calculate_path_distance(graph, path)

    return AlgorithmResult(
        algorithm="Dijkstra",
        start=start,
        destination=destination,
        path=path,
        distance_km=dist,
        nodes_explored=nodes_explored,
        execution_time_ms=round(elapsed_ms, 4),
        is_optimal_distance=True,
        notes="Dijkstra guarantees the globally optimal minimum-distance route without heuristic assumptions.",
    )
