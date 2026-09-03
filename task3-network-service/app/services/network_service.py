"""Application logic coordinating complete city-network analysis."""

from collections.abc import Callable
from time import perf_counter
from typing import Protocol, TypeVar

from app.algorithms.graph_builder import build_adjacency
from app.algorithms.metrics import (
    connection_counts,
    degree_centrality,
    most_connected_node,
    network_density,
    rank_by_degree_centrality,
)
from app.algorithms.traversal import breadth_first_search, depth_first_search
from app.models.network_models import (
    AvailableNode,
    AvailableNodesResponse,
    CentralityResult,
    Location,
    MostConnectedLocation,
    NetworkAnalysisResponse,
    Road,
    TraversalResult,
)


Result = TypeVar("Result")


class NetworkDataRepository(Protocol):
    """The database operations required by the analysis service."""

    def get_locations(self) -> list[Location]: ...

    def get_roads(self) -> list[Road]: ...


class InvalidStartNodeError(ValueError):
    """Raised when a requested traversal start is absent from the graph."""


def _timed(operation: Callable[[], Result]) -> tuple[Result, float]:
    """Run an operation and return its result plus elapsed milliseconds."""
    started = perf_counter()
    result = operation()
    return result, (perf_counter() - started) * 1000


class NetworkAnalysisService:
    """Coordinate repository data and the pure Task 3 graph algorithms."""

    def __init__(self, repository: NetworkDataRepository) -> None:
        self._repository = repository

    def list_nodes(self) -> AvailableNodesResponse:
        """Return selectable locations in deterministic key order."""
        locations = self._repository.get_locations()
        nodes = [
            AvailableNode(
                location_key=location.location_key,
                name=location.name,
                type=location.type,
            )
            for location in sorted(locations, key=lambda item: item.location_key)
        ]
        return AvailableNodesResponse(nodes=nodes)

    def analyze(self, start_node: str) -> NetworkAnalysisResponse:
        """Run all Task 3 analyses from ``start_node`` over repository data."""
        total_started = perf_counter()
        locations = self._repository.get_locations()
        roads = self._repository.get_roads()
        graph = build_adjacency(locations, roads)

        if start_node not in graph:
            raise InvalidStartNodeError(
                f"Start node {start_node!r} does not exist in the city network"
            )

        names = {location.location_key: location.name for location in locations}

        bfs_data, bfs_time = _timed(lambda: breadth_first_search(graph, start_node))
        dfs_data, dfs_time = _timed(lambda: depth_first_search(graph, start_node))

        metrics_started = perf_counter()
        counts = connection_counts(graph)
        centralities = degree_centrality(graph)
        ranking = rank_by_degree_centrality(graph)
        highest = most_connected_node(graph)
        density = network_density(graph)
        metrics_time = (perf_counter() - metrics_started) * 1000

        centrality_results = [
            CentralityResult(
                location_key=item["node"],
                name=names[item["node"]],
                degree=counts[item["node"]],
                centrality=centralities[item["node"]],
                rank=item["rank"],
            )
            for item in ranking
        ]

        most_connected = None
        if highest is not None:
            most_connected = MostConnectedLocation(
                location_key=highest["node"],
                name=names[highest["node"]],
                degree=highest["degree"],
                centrality=highest["centrality"],
            )

        total_time = (perf_counter() - total_started) * 1000
        return NetworkAnalysisResponse(
            start_node=start_node,
            start_location_name=names[start_node],
            total_nodes=len(graph),
            # A source road row is one edge record, regardless of its direction.
            total_edges=len(roads),
            most_connected_location=most_connected,
            network_density=density,
            bfs=TraversalResult(
                traversal_order=bfs_data[0],
                visited_count=bfs_data[1],
                execution_time_ms=bfs_time,
            ),
            dfs=TraversalResult(
                traversal_order=dfs_data[0],
                visited_count=dfs_data[1],
                execution_time_ms=dfs_time,
            ),
            centrality=centrality_results,
            metrics_execution_time_ms=metrics_time,
            total_execution_time_ms=total_time,
        )
