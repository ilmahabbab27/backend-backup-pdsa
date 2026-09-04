"""Comprehensive automated tests for Graph Algorithms (Task 1).

Covers all 8 specified test requirements:
  Test 1: Simple direct route.
  Test 2: Route containing multiple intermediate cities.
  Test 3: Weighted graph where the path with fewer edges is NOT the shortest-distance path.
          (Demonstrates fundamental distinction between BFS and Dijkstra/A*).
  Test 4: Unreachable destination (disconnected graph/island node).
  Test 5: Start equals destination.
  Test 6: Invalid city (not present in network).
  Test 7: Dijkstra and A* produce the exact same optimal distance on weighted networks.
  Test 8: Comparison of all three algorithms on the same journey.
"""

from app.algorithms.astar import astar_search
from app.algorithms.bfs import bfs_search
from app.algorithms.dijkstra import dijkstra_search
from app.algorithms.graph import Graph
from app.repositories.network_repository import NetworkRepository
from app.services.route_service import RouteService


def build_test_network() -> Graph:
    """Build a standard test graph with specific topological properties."""
    g = Graph(is_directed=False)

    # City vertices with coordinates
    g.add_node("city-hall", "City Hall", 6.9271, 79.8612)
    g.add_node("bus-station", "Bus Station", 6.9257, 79.8626)
    g.add_node("central-hospital", "Central Hospital", 6.9282, 79.8631)
    g.add_node("police-station", "Police Station", 6.9310, 79.8645)
    g.add_node("fire-station", "Fire Station", 6.9231, 79.8604)
    g.add_node("community-hospital", "Community Hospital", 6.9249, 79.8579)
    g.add_node("residential", "Residential", 6.9262, 79.8569)
    g.add_node("waste-center", "Waste Center", 6.9218, 79.8588)

    # Isolated node with no incident edges (disconnected graph test)
    g.add_node("isolated-outpost", "Isolated Outpost", 6.9950, 79.9500)

    # Roads
    # KEY TEST 3 SETUP:
    # city-hall -> central-hospital: direct 1-hop road with distance 8.0 km.
    # city-hall -> bus-station (1.2 km) -> central-hospital (2.8 km): 2-hop road with distance 4.0 km.
    g.add_edge("city-hall", "central-hospital", distance_km=8.0)
    g.add_edge("city-hall", "bus-station", distance_km=1.2)
    g.add_edge("bus-station", "central-hospital", distance_km=2.8)

    # Multi-hop chain for Test 2
    g.add_edge("city-hall", "police-station", distance_km=1.0)
    g.add_edge("police-station", "fire-station", distance_km=1.5)
    g.add_edge("fire-station", "community-hospital", distance_km=2.2)
    g.add_edge("community-hospital", "residential", distance_km=1.4)
    g.add_edge("residential", "waste-center", distance_km=3.3)

    return g


# ==============================================================================
# TEST 1: Simple direct route
# ==============================================================================
def test_1_simple_direct_route():
    """Verify that a direct connection is correctly identified and traversed."""
    g = build_test_network()

    dijkstra_res = dijkstra_search(g, "city-hall", "bus-station")
    assert dijkstra_res.path == ["city-hall", "bus-station"]
    assert dijkstra_res.distance_km == 1.2
    assert dijkstra_res.hops == 1

    astar_res = astar_search(g, "city-hall", "bus-station")
    assert astar_res.path == ["city-hall", "bus-station"]
    assert astar_res.distance_km == 1.2

    bfs_res = bfs_search(g, "city-hall", "bus-station")
    assert bfs_res.path == ["city-hall", "bus-station"]
    assert bfs_res.distance_km == 1.2


# ==============================================================================
# TEST 2: Route containing multiple intermediate cities
# ==============================================================================
def test_2_multi_intermediate_cities_route():
    """Verify multi-hop path traversal across multiple consecutive intermediate nodes."""
    g = build_test_network()

    # Path from city-hall to residential requires traversing police-station, fire-station, community-hospital
    res = dijkstra_search(g, "city-hall", "residential")
    expected_path = [
        "city-hall",
        "police-station",
        "fire-station",
        "community-hospital",
        "residential",
    ]
    assert res.path == expected_path
    # Distances: 1.0 + 1.5 + 2.2 + 1.4 = 6.1 km
    assert abs(res.distance_km - 6.1) < 1e-4
    assert res.hops == 4
    assert res.nodes_explored >= 4


# ==============================================================================
# TEST 3: Path with fewer edges is NOT the shortest-distance path
# ==============================================================================
def test_3_fewer_edges_is_not_shortest_distance():
    """CRITICAL TEST: Demonstrate fundamental difference between BFS and Dijkstra/A*.

    In this graph:
      Path 1: city-hall -> central-hospital
              Hops: 1
              Distance: 8.0 km
      Path 2: city-hall -> bus-station -> central-hospital
              Hops: 2
              Distance: 1.2 + 2.8 = 4.0 km

    BFS must choose Path 1 (fewest hops = 1).
    Dijkstra and A* must choose Path 2 (minimum physical distance = 4.0 km).
    """
    g = build_test_network()

    bfs_res = bfs_search(g, "city-hall", "central-hospital")
    dijkstra_res = dijkstra_search(g, "city-hall", "central-hospital")
    astar_res = astar_search(g, "city-hall", "central-hospital")

    # BFS picks the 1-hop path because it finds minimum edges
    assert bfs_res.path == ["city-hall", "central-hospital"]
    assert bfs_res.hops == 1
    assert bfs_res.distance_km == 8.0

    # Dijkstra picks the 2-hop path because 4.0 km < 8.0 km
    assert dijkstra_res.path == ["city-hall", "bus-station", "central-hospital"]
    assert dijkstra_res.hops == 2
    assert dijkstra_res.distance_km == 4.0

    # A* also picks the 2-hop path with 4.0 km optimal distance
    assert astar_res.path == ["city-hall", "bus-station", "central-hospital"]
    assert astar_res.hops == 2
    assert astar_res.distance_km == 4.0

    # Explicit assertion of the divergence:
    assert dijkstra_res.distance_km < bfs_res.distance_km
    assert bfs_res.hops < dijkstra_res.hops


# ==============================================================================
# TEST 4: Unreachable destination (disconnected graph)
# ==============================================================================
def test_4_unreachable_destination():
    """Verify that an unreachable/disconnected node is handled gracefully without crashing."""
    g = build_test_network()

    bfs_res = bfs_search(g, "city-hall", "isolated-outpost")
    assert bfs_res.path == []
    assert bfs_res.distance_km == 0.0

    dijkstra_res = dijkstra_search(g, "city-hall", "isolated-outpost")
    assert dijkstra_res.path == []
    assert dijkstra_res.distance_km == 0.0

    astar_res = astar_search(g, "city-hall", "isolated-outpost")
    assert astar_res.path == []
    assert astar_res.distance_km == 0.0


# ==============================================================================
# TEST 5: Start equals destination
# ==============================================================================
def test_5_start_equals_destination():
    """Verify behavior when start and destination are the exact same location."""
    g = build_test_network()

    for algo_fn in [bfs_search, dijkstra_search, astar_search]:
        res = algo_fn(g, "city-hall", "city-hall")
        assert res.path == ["city-hall"]
        assert res.distance_km == 0.0
        assert res.hops == 0
        assert res.nodes_explored == 1


# ==============================================================================
# TEST 6: Invalid / non-existent city
# ==============================================================================
def test_6_invalid_city():
    """Verify that invalid city keys return empty results safely."""
    g = build_test_network()

    bfs_res = bfs_search(g, "non-existent-city", "city-hall")
    assert bfs_res.path == []

    dijkstra_res = dijkstra_search(g, "city-hall", "unknown-place")
    assert dijkstra_res.path == []

    astar_res = astar_search(g, "invalid_1", "invalid_2")
    assert astar_res.path == []


# ==============================================================================
# TEST 7: Dijkstra and A* produce identical optimal distance on weighted graph
# ==============================================================================
def test_7_dijkstra_and_astar_produce_same_optimal_distance():
    """Verify that Dijkstra and A* return the exact same minimum distance across pairs."""
    repo = NetworkRepository()
    g = repo.build_graph()

    pairs = [
        ("city-hall", "residential"),
        ("central-hospital", "shopping-center"),
        ("police-station", "university"),
        ("fire-station", "riverside"),
        ("waste-center", "central-hospital"),
    ]

    for s, d in pairs:
        dijkstra_res = dijkstra_search(g, s, d)
        astar_res = astar_search(g, s, d)

        assert abs(dijkstra_res.distance_km - astar_res.distance_km) < 1e-4, (
            f"Distance mismatch for {s} -> {d}: "
            f"Dijkstra={dijkstra_res.distance_km}, A*={astar_res.distance_km}"
        )
        assert dijkstra_res.is_optimal_distance is True
        assert astar_res.is_optimal_distance is True


# ==============================================================================
# TEST 8: Compare all three algorithms
# ==============================================================================
def test_8_compare_all_three_algorithms():
    """Verify that compare_algorithms service runs all 3 algorithms and measures metrics."""
    service = RouteService()
    comp = service.compare_algorithms("city-hall", "central-hospital")

    assert comp.start == "city-hall"
    assert comp.destination == "central-hospital"
    assert len(comp.results) == 3

    algo_names = [r.algorithm for r in comp.results]
    assert "BFS" in algo_names
    assert "Dijkstra" in algo_names
    assert "A*" in algo_names

    # Check that execution times were actually measured (> 0.0)
    for r in comp.results:
        assert r.execution_time_ms >= 0.0
        assert r.nodes_explored > 0

    # Ensure analysis text describes the trade-offs
    assert "BFS" in comp.analysis
    assert "Dijkstra" in comp.analysis
