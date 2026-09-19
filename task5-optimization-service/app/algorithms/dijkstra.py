"""Dijkstra's shortest path algorithms and road network path reconstruction."""

from typing import Dict, List, Optional, Tuple
import networkx as nx

# T5DS: Checks if the road network is connected before route optimization begins.
def is_graph_connected(graph: nx.Graph) -> bool:
    """Check if the undirected road network graph is fully connected."""
    if graph is None or not isinstance(graph, nx.Graph) or graph.number_of_nodes() == 0:
        return False
    return nx.is_connected(graph)


# T5DS: Finds separate connected groups in the transport network for validation and debugging.
def get_connected_components(graph: nx.Graph) -> List[List[str]]:
    """Return all connected components (node ID lists) in the road network graph."""
    if graph is None or not isinstance(graph, nx.Graph):
        return []
    return [list(c) for c in nx.connected_components(graph)]


# T5DS: Computes all-pairs shortest distances across the route network for fleet optimization.
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
        ValueError: If graph is invalid, a target node does not exist in graph, or any pair is disconnected.
    """
    if graph is None or not isinstance(graph, nx.Graph):
        raise ValueError("Invalid graph provided for distance matrix computation.")

    if not target_nodes:
        return {}

    for node in target_nodes:
        if node not in graph:
            raise ValueError(f"Target node '{node}' not found in the road network graph.")

    distance_matrix: Dict[str, Dict[str, float]] = {u: {} for u in target_nodes}

    for source in target_nodes:
        # Use single-source Dijkstra to compute shortest distances from `source`
        try:
            lengths = nx.single_source_dijkstra_path_length(graph, source, weight="weight")
        except Exception as e:
            raise ValueError(f"Dijkstra calculation failed for source '{source}': {e}") from e

        for target in target_nodes:
            if target not in lengths:
                raise ValueError(
                    f"No navigable road path exists between '{source}' and '{target}'. "
                    "The graph might be disconnected."
                )
            distance_matrix[source][target] = round(float(lengths[target]), 4)

    return distance_matrix


# T5DS: Stores the shortest path sequence between all route points for downstream optimization logic.
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
    if graph is None or not isinstance(graph, nx.Graph):
        raise ValueError("Invalid graph provided for path matrix computation.")

    if not target_nodes:
        return {}

    for node in target_nodes:
        if node not in graph:
            raise ValueError(f"Target node '{node}' not found in the road network graph.")

    path_matrix: Dict[str, Dict[str, List[str]]] = {u: {} for u in target_nodes}

    for source in target_nodes:
        try:
            paths = nx.single_source_dijkstra_path(graph, source, weight="weight")
        except Exception as e:
            raise ValueError(f"Dijkstra path calculation failed for source '{source}': {e}") from e

        for target in target_nodes:
            if target not in paths:
                raise ValueError(f"No path found between '{source}' and '{target}'.")
            path_matrix[source][target] = paths[target]

    return path_matrix


# T5DS: Computes the shortest path cost and node sequence between two network nodes using Dijkstra.
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
    if graph is None or not isinstance(graph, nx.Graph):
        raise ValueError("Invalid graph provided.")

    if source not in graph:
        raise ValueError(f"Source node '{source}' not found in the road network graph.")
    if target not in graph:
        raise ValueError(f"Target node '{target}' not found in the road network graph.")

    try:
        dist, path = nx.single_source_dijkstra(graph, source, target, weight="weight")
        return round(float(dist), 4), path
    except nx.NetworkXNoPath:
        raise ValueError(f"No navigable path exists between '{source}' and '{target}'.")
    except Exception as e:
        raise ValueError(f"Error computing shortest path from '{source}' to '{target}': {e}") from e


# T5DS: Expands a stop sequence into a fully connected route across the road network.
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

        try:
            _, segment_nodes = compute_shortest_path(graph, src, dst)
        except Exception:
            # Fallback if graph calculation fails: connect endpoints directly
            segment_nodes = [src, dst]

        if not full_path:
            full_path.extend(segment_nodes)
        else:
            # Skip the first node of this segment as it is already the last node of full_path
            full_path.extend(segment_nodes[1:])

    return full_path

