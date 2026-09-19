"""A* (A-Star) Search Algorithm using admissible geographic heuristic."""

import heapq
import time
from typing import Callable, Optional

# T1DS: A* search algorithm using heuristic guidance to reach the target faster than plain Dijkstra.

from app.algorithms.graph import Graph, Node
from app.algorithms.helpers import calculate_path_distance, reconstruct_path
from app.algorithms.types import AlgorithmResult
from app.utils.geo import euclidean_distance, haversine_distance


def default_geographic_heuristic(graph: Graph) -> Callable[[str, str], float]:
    """Create a heuristic function calculating straight-line distance between nodes in km.

    If latitude/longitude coordinates are non-zero, uses the Haversine formula.
    If x/y coordinates are present and lat/lon are absent, uses scaled Euclidean distance.
    Straight-line geographic distance satisfies:
      1. Admissibility: h(n) <= true shortest distance h*(n)
      2. Consistency (monotonicity): h(u) <= c(u, v) + h(v) due to the triangle inequality.
    """

    def heuristic(u: str, goal: str) -> float:
        node_u: Optional[Node] = graph.get_node(u)
        node_goal: Optional[Node] = graph.get_node(goal)

        if not node_u or not node_goal:
            return 0.0

        # Check for valid lat/lon
        if (
            node_u.latitude != 0.0
            or node_u.longitude != 0.0
            or node_goal.latitude != 0.0
            or node_goal.longitude != 0.0
        ):
            return haversine_distance(
                node_u.latitude,
                node_u.longitude,
                node_goal.latitude,
                node_goal.longitude,
            )

        # Fallback to x/y if lat/lon not provided
        if (
            node_u.x is not None
            and node_u.y is not None
            and node_goal.x is not None
            and node_goal.y is not None
        ):
            # Scale factor 1/90 converts pixel coordinate space to approximately kilometers
            return euclidean_distance(
                node_u.x, node_u.y, node_goal.x, node_goal.y, scale_factor=0.011
            )

        return 0.0

    return heuristic


def astar_search(
    graph: Graph,
    start: str,
    destination: str,
    heuristic_fn: Optional[Callable[[str, str], float]] = None,
) -> AlgorithmResult:
    """Find the shortest physical distance route using A* Search.

    A* evaluates nodes by combining g(n) (the exact cost to reach node n from start)
    and h(n) (the estimated heuristic cost from n to destination):
        f(n) = g(n) + h(n)

    Because our geographic heuristic is admissible and consistent, A* is guaranteed
    to find the optimal (minimum-distance) path just like Dijkstra, while pruning
    branches that point away from the target, typically expanding fewer nodes.

    Complexity:
        Time: O((V + E) log V) in worst-case (identical to Dijkstra when h(n) = 0),
              but approaches O(b^d) or linear O(d) in practical search when h is well-informed.
        Space: O(V) for the open set priority queue, closed set, g-score map, and parent map.
    """
    t0 = time.perf_counter()

    if not graph.has_node(start) or not graph.has_node(destination):
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return AlgorithmResult(
            algorithm="A*",
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
            algorithm="A*",
            start=start,
            destination=destination,
            path=[start],
            distance_km=0.0,
            nodes_explored=1,
            execution_time_ms=round(elapsed_ms, 4),
            is_optimal_distance=True,
            notes="Start and destination are identical.",
        )

    h = heuristic_fn or default_geographic_heuristic(graph)

    # Priority queue stores tuples of (f_score, g_score, node_id)
    start_h = h(start, destination)
    pq: list[tuple[float, float, str]] = [(start_h, 0.0, start)]

    g_score: dict[str, float] = {start: 0.0}
    parent: dict[str, Optional[str]] = {start: None}
    closed_set: set[str] = set()
    nodes_explored = 0
    found = False

    while pq:
        f_val, current_g, current_node = heapq.heappop(pq)

        if current_node in closed_set:
            continue

        closed_set.add(current_node)
        nodes_explored += 1

        if current_node == destination:
            found = True
            break

        for neighbor, weight in graph.get_neighbors(current_node):
            if neighbor in closed_set:
                continue

            tentative_g = current_g + weight
            if tentative_g < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative_g
                parent[neighbor] = current_node
                h_val = h(neighbor, destination)
                f_score = tentative_g + h_val
                heapq.heappush(pq, (f_score, tentative_g, neighbor))

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if not found or destination not in parent:
        return AlgorithmResult(
            algorithm="A*",
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
        algorithm="A*",
        start=start,
        destination=destination,
        path=path,
        distance_km=dist,
        nodes_explored=nodes_explored,
        execution_time_ms=round(elapsed_ms, 4),
        is_optimal_distance=True,
        notes="A* achieves the optimal shortest path guided by straight-line geographic heuristic (Haversine).",
    )
