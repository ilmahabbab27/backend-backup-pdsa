"""Dijkstra's shortest path algorithms and road network path reconstruction."""

from typing import Dict, List, Tuple
import networkx as nx


def compute_distance_matrix(
    graph: nx.Graph,
    target_nodes: List[str],
) -> Dict[str, Dict[str, float]]:
    """Compute all-pairs shortest road distance matrix among a specified list of target nodes.

    Args:
        graph: The NetworkX graph representing the city road network with edge 'weight' (km).
        target_nodes: List of node IDs to compute pairwise distances between.

    Returns:
        A nested dictionary matrix where matrix[u][v] is the shortest distance in km from u to v.

    Raises:
        ValueError: If a target node does not exist in the graph or if any pair is disconnected.
    """
    for node in target_nodes:
        if node not in graph:
            raise ValueError(f"Target node '{node}' not found in the road network graph.")

    distance_matrix: Dict[str, Dict[str, float]] = {u: {} for u in target_nodes}

    for source in target_nodes:
        # Use single-source Dijkstra to compute shortest distances from `source`
        lengths = nx.single_source_dijkstra_path_length(graph, source, weight="weight")
        for target in target_nodes:
            if target not in lengths:
                raise ValueError(
                    f"No navigable road path exists between '{source}' and '{target}'. "
                    "The graph might be disconnected."
                )
            distance_matrix[source][target] = round(float(lengths[target]), 4)

    return distance_matrix


def compute_path_matrix(
    graph: nx.Graph,
    target_nodes: List[str],
) -> Dict[str, Dict[str, List[str]]]:
    """Compute all-pairs shortest paths (node sequences) among a specified list of target nodes.

    Args:
        graph: The NetworkX road network graph.
        target_nodes: List of node IDs.

    Returns:
        A nested dictionary where path_matrix[u][v] is the list of node IDs along the shortest path.

    Raises:
        ValueError: If any target node is missing or unreachable.
    """
    for node in target_nodes:
        if node not in graph:
            raise ValueError(f"Target node '{node}' not found in the road network graph.")

    path_matrix: Dict[str, Dict[str, List[str]]] = {u: {} for u in target_nodes}

    for source in target_nodes:
        paths = nx.single_source_dijkstra_path(graph, source, weight="weight")
        for target in target_nodes:
            if target not in paths:
                raise ValueError(f"No path found between '{source}' and '{target}'.")
            path_matrix[source][target] = paths[target]

    return path_matrix


def compute_shortest_path(
    graph: nx.Graph,
    source: str,
    target: str,
) -> Tuple[float, List[str]]:
    """Compute the shortest path length and node sequence between source and target.

    Args:
        graph: The NetworkX road network graph.
        source: Source node ID.
        target: Target node ID.

    Returns:
        A tuple (distance_km, [node_1, node_2, ..., node_k]).
    """
    if source not in graph:
        raise ValueError(f"Source node '{source}' not found in the road network graph.")
    if target not in graph:
        raise ValueError(f"Target node '{target}' not found in the road network graph.")

    try:
        dist, path = nx.single_source_dijkstra(graph, source, target, weight="weight")
        return round(float(dist), 4), path
    except nx.NetworkXNoPath:
        raise ValueError(f"No navigable path exists between '{source}' and '{target}'.")


def reconstruct_full_path(
    graph: nx.Graph,
    stop_sequence: List[str],
) -> List[str]:
    """Expand a high-level stop sequence into a complete turn-by-turn intersection path.

    For example, converting ['D0', 'B1', 'T1', 'D0'] into
    ['D0', 'I1', 'B1', 'I2', 'T1', 'I3', 'D0'] by finding Dijkstra shortest paths
    between consecutive stops and removing adjacent duplicate junction nodes.

    Args:
        graph: The NetworkX road network graph.
        stop_sequence: List of high-level stop node IDs.

    Returns:
        Full list of visited node IDs including intermediate intersections.
    """
    if not stop_sequence:
        return []
    if len(stop_sequence) == 1:
        return [stop_sequence[0]]

    full_path: List[str] = []

    for i in range(len(stop_sequence) - 1):
        src = stop_sequence[i]
        dst = stop_sequence[i + 1]

        if src == dst:
            if not full_path:
                full_path.append(src)
            continue

        _, segment_nodes = compute_shortest_path(graph, src, dst)

        if not full_path:
            full_path.extend(segment_nodes)
        else:
            # Skip the first node of this segment as it is already the last node of full_path
            full_path.extend(segment_nodes[1:])

    return full_path
