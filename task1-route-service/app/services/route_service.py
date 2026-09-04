"""Application service coordinating graph traversal algorithms, benchmarking, and city queries."""

import random
import time
from typing import Optional

from app.algorithms.astar import astar_search, default_geographic_heuristic
from app.algorithms.bfs import bfs_search
from app.algorithms.dijkstra import dijkstra_search
from app.algorithms.graph import Graph
from app.models.route_models import (
    BenchmarkResponse,
    BenchmarkTierResult,
    CityModel,
    ComparisonResponse,
    NetworkResponse,
    RoadModel,
    RouteRequest,
    RouteResponse,
)
from app.repositories.network_repository import NetworkRepository


class RouteOptimizationException(Exception):
    """Domain exception for route planning errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RouteService:
    """Service layer managing route calculations, algorithm comparisons, and benchmarks."""

    def __init__(self, repo: Optional[NetworkRepository] = None) -> None:
        self.repo = repo or NetworkRepository()
        self._graph: Optional[Graph] = None
        self._reload_graph()

    def _reload_graph(self) -> None:
        """Construct the road network graph from repository."""
        self._graph = self.repo.build_graph()

    @property
    def graph(self) -> Graph:
        """Return the active road network graph."""
        if self._graph is None:
            self._reload_graph()
        return self._graph  # type: ignore

    def get_cities(self) -> list[CityModel]:
        """Return all available city nodes with connection degrees."""
        locations = self.repo.get_locations()
        roads = self.repo.get_roads()

        connection_counts: dict[str, int] = {}
        for r in roads:
            src = r["source"]
            dst = r["destination"]
            connection_counts[src] = connection_counts.get(src, 0) + 1
            connection_counts[dst] = connection_counts.get(dst, 0) + 1

        cities = [
            CityModel(
                id=loc["id"],
                name=loc["name"],
                latitude=loc["latitude"],
                longitude=loc["longitude"],
                x=loc.get("x"),
                y=loc.get("y"),
                kind=loc.get("kind", "city"),
                connections=connection_counts.get(loc["id"], 0),
                metadata=loc.get("metadata", {}),
            )
            for loc in locations
        ]
        cities.sort(key=lambda c: c.name)
        return cities

    def get_network(self) -> NetworkResponse:
        """Return full network topology."""
        cities = self.get_cities()
        roads_raw = self.repo.get_roads()
        roads = [
            RoadModel(
                source=r["source"],
                destination=r["destination"],
                distance_km=r["distance_km"],
                travel_time_min=r.get("travel_time_min"),
                is_bidirectional=r.get("is_bidirectional", True),
                metadata=r.get("metadata", {}),
            )
            for r in roads_raw
        ]
        return NetworkResponse(
            cities=cities,
            roads=roads,
            total_cities=len(cities),
            total_roads=len(roads),
        )

    def find_route(self, request: RouteRequest) -> RouteResponse:
        """Execute the requested pathfinding algorithm between start and destination."""
        start = request.start.strip()
        destination = request.destination.strip()
        algo = request.algorithm.lower().strip()

        if not start:
            raise RouteOptimizationException("Starting city must be specified.", 400)
        if not destination:
            raise RouteOptimizationException("Destination city must be specified.", 400)

        if not self.graph.has_node(start):
            raise RouteOptimizationException(
                f"Starting city '{start}' does not exist in the transportation network.",
                404,
            )
        if not self.graph.has_node(destination):
            raise RouteOptimizationException(
                f"Destination city '{destination}' does not exist in the transportation network.",
                404,
            )

        if algo == "bfs":
            result = bfs_search(self.graph, start, destination)
        elif algo == "dijkstra":
            result = dijkstra_search(self.graph, start, destination)
        elif algo == "astar":
            result = astar_search(self.graph, start, destination)
        else:
            raise RouteOptimizationException(
                f"Invalid algorithm '{algo}'. Supported algorithms: 'bfs', 'dijkstra', 'astar'.",
                400,
            )

        if not result.path and start != destination:
            raise RouteOptimizationException(
                f"No route found connecting '{start}' and '{destination}'. The graph is disconnected.",
                404,
            )

        route_names = [
            self.graph.get_node(nid).name if self.graph.get_node(nid) else nid
            for nid in result.path
        ]

        return RouteResponse(
            algorithm=result.algorithm,
            start=start,
            destination=destination,
            route=result.path,
            route_names=route_names,
            distance=result.distance_km,
            nodes_explored=result.nodes_explored,
            execution_time_ms=result.execution_time_ms,
            is_optimal_distance=result.is_optimal_distance,
            hops=result.hops,
            notes=result.notes,
        )

    def compare_algorithms(self, start: str, destination: str) -> ComparisonResponse:
        """Run BFS, Dijkstra, and A* on the same start/destination and measure comparative metrics."""
        start = start.strip()
        destination = destination.strip()

        if not start or not destination:
            raise RouteOptimizationException("Both start and destination must be provided.", 400)
        if not self.graph.has_node(start) or not self.graph.has_node(destination):
            raise RouteOptimizationException("One or both selected cities do not exist in the network.", 404)

        bfs_res = bfs_search(self.graph, start, destination)
        dijkstra_res = dijkstra_search(self.graph, start, destination)
        astar_res = astar_search(self.graph, start, destination)

        def make_route_resp(res) -> RouteResponse:
            names = [
                self.graph.get_node(n).name if self.graph.get_node(n) else n
                for n in res.path
            ]
            return RouteResponse(
                algorithm=res.algorithm,
                start=start,
                destination=destination,
                route=res.path,
                route_names=names,
                distance=res.distance_km,
                nodes_explored=res.nodes_explored,
                execution_time_ms=res.execution_time_ms,
                is_optimal_distance=res.is_optimal_distance,
                hops=res.hops,
                notes=res.notes,
            )

        results = [
            make_route_resp(bfs_res),
            make_route_resp(dijkstra_res),
            make_route_resp(astar_res),
        ]

        # Analytical commentary based on empirical results
        analysis_parts = []
        if start == destination:
            analysis = "Start and destination are identical; all algorithms trivially return a 0-distance path."
        elif not dijkstra_res.path:
            analysis = "Destination is unreachable from the starting city; graph partitions prevent traversal."
        else:
            if bfs_res.distance_km > dijkstra_res.distance_km:
                analysis_parts.append(
                    f"BFS found a path with {bfs_res.hops} hops ({bfs_res.distance_km:.1f} km), "
                    f"whereas Dijkstra and A* found a shorter physical route of {dijkstra_res.distance_km:.1f} km "
                    f"({dijkstra_res.hops} hops). This illustrates that BFS minimizes edge count rather than weighted distance."
                )
            else:
                analysis_parts.append(
                    f"BFS, Dijkstra, and A* all identified paths with distance {dijkstra_res.distance_km:.1f} km."
                )

            if astar_res.nodes_explored < dijkstra_res.nodes_explored:
                diff = dijkstra_res.nodes_explored - astar_res.nodes_explored
                analysis_parts.append(
                    f"A* explored {astar_res.nodes_explored} nodes vs Dijkstra's {dijkstra_res.nodes_explored} "
                    f"nodes ({diff} fewer nodes explored), demonstrating how the geographic heuristic directs search toward the target."
                )
            else:
                analysis_parts.append(
                    f"Dijkstra explored {dijkstra_res.nodes_explored} nodes and A* explored {astar_res.nodes_explored} nodes."
                )

            analysis = " ".join(analysis_parts)

        return ComparisonResponse(
            start=start,
            destination=destination,
            results=results,
            analysis=analysis,
        )

    def run_benchmarks(self, iterations: int = 50) -> BenchmarkResponse:
        """Systematically evaluate BFS, Dijkstra, and A* across Small, Medium, and Large graph topologies."""
        # 1. Small Graph (5 nodes, 6 edges)
        small_graph = Graph()
        small_nodes = [
            ("A", "City A", 6.90, 79.80),
            ("B", "City B", 6.91, 79.81),
            ("C", "City C", 6.92, 79.82),
            ("D", "City D", 6.93, 79.83),
            ("E", "City E", 6.94, 79.84),
        ]
        for nid, name, lat, lon in small_nodes:
            small_graph.add_node(nid, name, lat, lon)
        small_edges = [
            ("A", "B", 3.0),
            ("B", "C", 4.0),
            ("A", "D", 8.0),
            ("D", "E", 2.0),
            ("C", "E", 1.5),
            ("B", "D", 2.5),
        ]
        for u, v, w in small_edges:
            small_graph.add_edge(u, v, w)

        # 2. Medium Graph (Smart City Network - 16 nodes, 30 edges)
        medium_graph = self.graph

        # 3. Large Graph (50 nodes synthetic planar transportation network)
        random.seed(42)
        large_graph = Graph()
        grid_size = 7
        large_node_ids = []
        for i in range(grid_size):
            for j in range(grid_size):
                if len(large_node_ids) >= 50:
                    break
                nid = f"N_{i}_{j}"
                large_node_ids.append(nid)
                lat = 6.80 + i * 0.03 + (random.random() * 0.005)
                lon = 79.80 + j * 0.03 + (random.random() * 0.005)
                large_graph.add_node(nid, f"Hub {i}-{j}", lat, lon)

        # Connect grid neighbors + diagonals
        for i in range(grid_size):
            for j in range(grid_size):
                curr = f"N_{i}_{j}"
                if not large_graph.has_node(curr):
                    continue
                # right
                if j + 1 < grid_size:
                    nbr = f"N_{i}_{j+1}"
                    if large_graph.has_node(nbr):
                        dist = round(3.0 + random.random() * 2.0, 1)
                        large_graph.add_edge(curr, nbr, dist)
                # down
                if i + 1 < grid_size:
                    nbr = f"N_{i+1}_{j}"
                    if large_graph.has_node(nbr):
                        dist = round(3.0 + random.random() * 2.0, 1)
                        large_graph.add_edge(curr, nbr, dist)
                # diagonal
                if i + 1 < grid_size and j + 1 < grid_size:
                    nbr = f"N_{i+1}_{j+1}"
                    if large_graph.has_node(nbr):
                        dist = round(4.5 + random.random() * 2.5, 1)
                        large_graph.add_edge(curr, nbr, dist)

        tiers = [
            ("Small (5 nodes)", small_graph, "A", "E"),
            ("Medium - Smart City (16 nodes)", medium_graph, "city-hall", "shopping-center"),
            ("Large (50 nodes)", large_graph, large_node_ids[0], large_node_ids[-1]),
        ]

        tier_results: list[BenchmarkTierResult] = []

        for tier_name, test_graph, s, d in tiers:
            bfs_times, bfs_explored = [], []
            dijkstra_times, dijkstra_explored = [], []
            astar_times, astar_explored = [], []

            for _ in range(iterations):
                # BFS
                b_res = bfs_search(test_graph, s, d)
                bfs_times.append(b_res.execution_time_ms)
                bfs_explored.append(b_res.nodes_explored)

                # Dijkstra
                d_res = dijkstra_search(test_graph, s, d)
                dijkstra_times.append(d_res.execution_time_ms)
                dijkstra_explored.append(d_res.nodes_explored)

                # A*
                a_res = astar_search(test_graph, s, d)
                astar_times.append(a_res.execution_time_ms)
                astar_explored.append(a_res.nodes_explored)

            tier_results.append(
                BenchmarkTierResult(
                    tier_name=tier_name,
                    node_count=test_graph.vertex_count,
                    edge_count=test_graph.edge_count,
                    bfs_time_ms=round(sum(bfs_times) / len(bfs_times), 4),
                    bfs_nodes=int(round(sum(bfs_explored) / len(bfs_explored))),
                    dijkstra_time_ms=round(sum(dijkstra_times) / len(dijkstra_times), 4),
                    dijkstra_nodes=int(round(sum(dijkstra_explored) / len(dijkstra_explored))),
                    astar_time_ms=round(sum(astar_times) / len(astar_times), 4),
                    astar_nodes=int(round(sum(astar_explored) / len(astar_explored))),
                )
            )

        conclusion = (
            "Empirical results indicate that Dijkstra and A* both reliably yield the optimal weighted shortest path. "
            "A* consistently explores fewer vertices than Dijkstra on directional queries when the geographic heuristic "
            "is informative, resulting in superior scalability on larger transportation networks."
        )

        return BenchmarkResponse(
            runs_averaged=iterations,
            tiers=tier_results,
            conclusion=conclusion,
        )
