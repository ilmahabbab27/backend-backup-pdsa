"""Pure metrics for undirected simple graphs."""

from collections.abc import Hashable, Iterable, Mapping
from typing import TypedDict, TypeVar


Node = TypeVar("Node", bound=Hashable)
Adjacency = Mapping[Node, Iterable[Node]]


class RankedNode(TypedDict):
    """A node's degree metrics and deterministic position in the ranking."""

    node: Node
    degree: int
    centrality: float
    rank: int


def connection_counts(graph: Adjacency[Node]) -> dict[Node, int]:
    """Return the number of distinct directly connected neighbours per node."""
    return {node: len(set(neighbours)) for node, neighbours in graph.items()}


def degree_centrality(graph: Adjacency[Node]) -> dict[Node, float]:
    """Return normalized degree centrality for every node in ``graph``."""
    vertex_count = len(graph)
    if vertex_count <= 1:
        return {node: 0.0 for node in graph}

    denominator = vertex_count - 1
    return {
        node: degree / denominator
        for node, degree in connection_counts(graph).items()
    }


def rank_by_degree_centrality(graph: Adjacency[Node]) -> list[RankedNode]:
    """Rank nodes by descending centrality, breaking ties by node text."""
    counts = connection_counts(graph)
    centralities = degree_centrality(graph)
    ordered_nodes = sorted(
        graph,
        key=lambda node: (-centralities[node], str(node)),
    )

    return [
        {
            "node": node,
            "degree": counts[node],
            "centrality": centralities[node],
            "rank": index,
        }
        for index, node in enumerate(ordered_nodes, start=1)
    ]


def most_connected_node(graph: Adjacency[Node]) -> RankedNode | None:
    """Return the highest-ranked node, or ``None`` for an empty graph."""
    ranking = rank_by_degree_centrality(graph)
    return ranking[0] if ranking else None


def network_density(graph: Adjacency[Node]) -> float:
    """Return density for an undirected simple graph.

    Each unordered pair is counted once even though a conventional undirected
    adjacency dictionary contains the road in both directions. Self-loops do
    not contribute to simple-graph density.
    """
    vertex_count = len(graph)
    if vertex_count <= 1:
        return 0.0

    edges = {
        frozenset((node, neighbour))
        for node, neighbours in graph.items()
        for neighbour in set(neighbours)
        if neighbour != node
    }
    return (2 * len(edges)) / (vertex_count * (vertex_count - 1))
