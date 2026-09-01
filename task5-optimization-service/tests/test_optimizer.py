"""Comprehensive unit and integration test suite for Waste Route Optimization Service."""

import math
import pytest
from fastapi.testclient import TestClient
import networkx as nx

from app.algorithms.clarke_wright import (
    ClarkeWrightOptimizer,
    calculate_route_distance,
    partition_bins_ffd,
    select_feasible_bins_ffd,
    solve_by_truck_partition,
    solve_fleet_routing,
    two_opt_sequence,
)
from app.algorithms.dijkstra import (
    compute_distance_matrix,
    compute_path_matrix,
    compute_shortest_path,
    get_connected_components,
    is_graph_connected,
    reconstruct_full_path,
)
from app.config.settings import Settings
from app.main import app
from app.models.schemas import OptimizationRequest
from app.repositories.map_repository import MapRepository
from app.services.optimizer_service import OptimizerService
from app.utils.exceptions import (
    CapacityExceededException,
    GraphTopologyException,
    InfeasibleRoutingException,
    OverweightBinException,
)
from app.utils.profiler import Profiler

client = TestClient(app)



# ---------------------------------------------------------
# 1. MapRepository Tests
# ---------------------------------------------------------

def test_map_repository_loads_nodes_and_graph() -> None:
    """Test that MapRepository successfully loads nodes, bins, and builds a connected NetworkX graph."""
    repo = MapRepository()
    graph = repo.get_graph()

    assert isinstance(graph, nx.Graph)
    assert graph.number_of_nodes() >= 37  # >= 1 Depot + 1 Dump + Intersections + Bins
    assert graph.number_of_edges() >= 42
    assert nx.is_connected(graph)

    # Check start depot
    start_nodes = repo.get_nodes_by_type("start")
    assert len(start_nodes) >= 1
    assert start_nodes[0].id == "D0"
    assert start_nodes[0].weight_kg == 0

    # Check destination station
    dest_nodes = repo.get_nodes_by_type("destination")
    assert len(dest_nodes) >= 1
    assert dest_nodes[0].id == "T1"
    assert dest_nodes[0].weight_kg == 0

    # Check intersections
    intersections = repo.get_nodes_by_type("intersection")
    assert len(intersections) >= 20
    for inter in intersections:
        assert inter.weight_kg == 0

    # Check smart bins (all bins have uniform static capacity of 400kg)
    bins = repo.get_nodes_by_type("bin")
    assert len(bins) >= 15
    for b in bins:
        assert b.weight_kg == 400


def test_map_repository_node_dict_and_lookup() -> None:
    """Test node dictionary retrieval and single node lookup."""
    repo = MapRepository()
    nodes_dict = repo.get_node_dict()

    assert "D0" in nodes_dict
    assert "T1" in nodes_dict
    assert "B1" in nodes_dict
    assert "I1" in nodes_dict

    d0 = repo.get_node("D0")
    assert d0.type == "start"

    t1 = repo.get_node("T1")
    assert t1.type == "destination"

    i1 = repo.get_node("I1")
    assert i1.type == "intersection"

    b1 = repo.get_node("B1")
    assert b1.type == "bin"

    with pytest.raises(KeyError):
        repo.get_node("NON_EXISTENT_NODE")


def test_nodes_have_required_fields_across_all_tiers() -> None:
    """Test that all nodes across Tier 1, 2, and 3 maps have valid coordinates and types."""
    for map_file in ["city_map_tier1_sparse.json", "city_map_tier2_medium.json", "city_map_tier3_dense.json"]:
        repo = MapRepository(map_path=f"data/{map_file}")
        intersections = repo.get_nodes_by_type("intersection")
        assert len(intersections) > 0
        for inter in intersections:
            assert inter.lat != 0.0 or inter.lon != 0.0 or inter.id is not None
            assert inter.weight_kg == 0

        bins = repo.get_nodes_by_type("bin")
        assert len(bins) > 0
        for b in bins:
            assert b.weight_kg > 0

        depots = repo.get_nodes_by_type("start")
        assert len(depots) == 1
        assert depots[0].id == "D0"

        destinations = repo.get_nodes_by_type("destination")
        assert len(destinations) == 1
        assert destinations[0].id == "T1"


def test_map_repository_full_map_response() -> None:
    """Test that full map response contains nodes and adjacency list."""
    repo = MapRepository()
    full_map = repo.get_full_map()

    assert len(full_map.nodes) >= 57
    assert len(full_map.adjacency_list) >= 57
    assert len(full_map.edges) >= 57


# ---------------------------------------------------------
# 2. Dijkstra Algorithm & Path Reconstruction Tests
# ---------------------------------------------------------

def test_dijkstra_shortest_path_calculation() -> None:
    """Test shortest path distance and waypoint sequence between known nodes."""
    repo = MapRepository()
    graph = repo.get_graph()

    # D0 to T1 shortest path
    dist_km, path = compute_shortest_path(graph, "D0", "T1")
    assert dist_km > 0.0
    assert path[0] == "D0"
    assert path[-1] == "T1"
    assert len(path) >= 2

    # Direct / single hop test
    dist_self, path_self = compute_shortest_path(graph, "D0", "D0")
    assert dist_self == 0.0
    assert path_self == ["D0"]


def test_dijkstra_all_pairs_distance_matrix() -> None:
    """Test all-pairs distance matrix computation for key POIs."""
    repo = MapRepository()
    graph = repo.get_graph()
    sample_nodes = ["D0", "T1", "B1", "B2"]

    matrix = compute_distance_matrix(graph, sample_nodes)

    assert set(matrix.keys()) == set(sample_nodes)
    for u in sample_nodes:
        assert set(matrix[u].keys()) == set(sample_nodes)
        assert matrix[u][u] == 0.0
        for v in sample_nodes:
            assert matrix[u][v] >= 0.0
            # Undirected symmetric distance
            assert abs(matrix[u][v] - matrix[v][u]) < 1e-4


def test_reconstruct_full_path_with_intersections() -> None:
    """Test intermediate road intersection expansion from high-level stop sequence."""
    repo = MapRepository()
    graph = repo.get_graph()

    stop_sequence = ["D0", "B1", "T1", "D0"]
    full_path = reconstruct_full_path(graph, stop_sequence)

    assert full_path[0] == "D0"
    assert full_path[-1] == "D0"
    assert "B1" in full_path
    assert "T1" in full_path
    # Intersections must expand the path beyond just the 4 key stops
    assert len(full_path) >= 4

    # Verify no adjacent duplicates
    for i in range(len(full_path) - 1):
        assert full_path[i] != full_path[i + 1]


def test_dijkstra_missing_node_raises_error() -> None:
    """Test that requesting path for non-existent node raises ValueError."""
    repo = MapRepository()
    graph = repo.get_graph()

    with pytest.raises(ValueError, match="Source node 'NON_EXISTENT' not found"):
        compute_shortest_path(graph, "NON_EXISTENT", "T1")

    with pytest.raises(ValueError, match="Target node 'NON_EXISTENT' not found"):
        compute_shortest_path(graph, "D0", "NON_EXISTENT")


def test_dijkstra_disconnected_graph_raises_error() -> None:
    """Test error handling when two subgraphs have no navigable connecting edges."""
    disconnected_graph = nx.Graph()
    disconnected_graph.add_node("A")
    disconnected_graph.add_node("B")

    with pytest.raises(ValueError, match="No navigable road path exists"):
        compute_distance_matrix(disconnected_graph, ["A", "B"])

    with pytest.raises(ValueError, match="Target node 'Z' not found"):
        compute_distance_matrix(disconnected_graph, ["Z"])


# ---------------------------------------------------------
# 3. Clarke-Wright Savings & FFD Packing Algorithm Tests
# ---------------------------------------------------------

def test_select_feasible_bins_ffd() -> None:
    """Test First-Fit Decreasing bin selection heuristic."""
    bins = [
        {"id": "B1", "weight_kg": 400},
        {"id": "B2", "weight_kg": 400},
        {"id": "B3", "weight_kg": 400},
        {"id": "B4", "weight_kg": 400},
        {"id": "B5", "weight_kg": 800},  # Overweight for 500kg truck
    ]
    # 2 trucks with 500kg capacity = 1000kg max
    packed, uncollected = select_feasible_bins_ffd(bins, truck_count=2, truck_capacity_kg=500)

    # Overweight bin B5 must be uncollected
    assert any(b["id"] == "B5" for b in uncollected)

    # Packed bins must not exceed individual or total capacity
    packed_weight = sum(b["weight_kg"] for b in packed)
    assert packed_weight <= 1000
    assert len(packed) >= 2


def test_clarke_wright_savings_merging() -> None:
    """Test Clarke-Wright Savings algorithm merges two proximal bins into one truck route."""
    # Synthetic distance matrix where B1 and B2 are close to each other
    dist_matrix = {
        "D0": {"D0": 0.0, "T1": 5.0, "B1": 2.0, "B2": 2.5},
        "T1": {"D0": 5.0, "T1": 0.0, "B1": 2.5, "B2": 2.0},
        "B1": {"D0": 2.0, "T1": 2.5, "B1": 0.0, "B2": 0.5},
        "B2": {"D0": 2.5, "T1": 2.0, "B1": 0.5, "B2": 0.0},
    }
    bins_data = [
        {"id": "B1", "weight_kg": 400},
        {"id": "B2", "weight_kg": 400},
    ]

    # With 1 truck with 1000kg capacity, B1 and B2 should be merged into 1 route
    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=bins_data,
        dist_matrix=dist_matrix,
        truck_count=1,
        truck_capacity_kg=1000,
    )

    assert len(results) == 1
    assert set(results[0].bins) == {"B1", "B2"}
    assert results[0].collected_weight_kg == 800
    assert results[0].stop_sequence[0] == "D0"
    assert results[0].stop_sequence[-2] == "T1"
    assert results[0].stop_sequence[-1] == "D0"


def test_clarke_wright_subset_truck() -> None:
    """Test route sequencing when 1 truck has sufficient capacity for a subset of bins."""
    repo = MapRepository()
    graph = repo.get_graph()
    bins = repo.get_nodes_by_type("bin")[:5]
    total_bin_weight = sum(b.weight_kg for b in bins)

    poi_ids = ["D0", "T1"] + [b.id for b in bins]
    dist_matrix = compute_distance_matrix(graph, poi_ids)
    bins_data = [{"id": b.id, "weight_kg": b.weight_kg} for b in bins]

    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=bins_data,
        dist_matrix=dist_matrix,
        truck_count=1,
        truck_capacity_kg=total_bin_weight + 500,
    )

    assert len(results) == 1
    truck_res = results[0]
    assert truck_res.truck_id == "TRUCK-1"
    assert set(truck_res.bins) == {b.id for b in bins}
    assert truck_res.collected_weight_kg == total_bin_weight
    assert truck_res.stop_sequence[0] == "D0"
    assert truck_res.stop_sequence[-2] == "T1"
    assert truck_res.stop_sequence[-1] == "D0"
    assert total_dist > 0.0


def test_clarke_wright_multi_truck_partitioning() -> None:
    """Test that bins are partitioned correctly across trucks respecting capacity constraints."""
    repo = MapRepository()
    graph = repo.get_graph()
    bins = repo.get_nodes_by_type("bin")
    truck_cap = 1500
    max_bins_per_truck = max(1, truck_cap // 400)
    truck_count = math.ceil(len(bins) / max_bins_per_truck) + 5

    poi_ids = ["D0", "T1"] + [b.id for b in bins]
    dist_matrix = compute_distance_matrix(graph, poi_ids)
    bins_data = [{"id": b.id, "weight_kg": b.weight_kg} for b in bins]

    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=bins_data,
        dist_matrix=dist_matrix,
        truck_count=truck_count,
        truck_capacity_kg=truck_cap,
    )

    assert len(results) >= 5
    all_collected_bins = []
    for res in results:
        assert res.collected_weight_kg <= truck_cap
        assert res.stop_sequence[0] == "D0"
        assert res.stop_sequence[-2] == "T1"
        assert res.stop_sequence[-1] == "D0"
        all_collected_bins.extend(res.bins)

    # All bins must be collected exactly once
    assert sorted(all_collected_bins) == sorted([b.id for b in bins])


def test_clarke_wright_empty_bins() -> None:
    """Test optimizer behavior when there are no bins to collect."""
    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=[],
        dist_matrix={"D0": {"D0": 0.0, "T1": 1.8}, "T1": {"D0": 1.8, "T1": 0.0}},
        truck_count=2,
        truck_capacity_kg=1000,
    )

    assert results == []
    assert total_dist == 0.0


# ---------------------------------------------------------
# 4. Profiler Utility Tests
# ---------------------------------------------------------

def test_profiler_context_manager() -> None:
    """Test that Profiler correctly records execution time and peak memory."""
    with Profiler() as prof:
        _ = [i ** 2 for i in range(100_000)]

    assert prof.execution_time_ms >= 0.0
    assert prof.peak_memory_kb >= 0.0


# ---------------------------------------------------------
# 5. API Integration & Fallback Tests
# ---------------------------------------------------------

def test_api_get_map() -> None:
    """Test GET /api/v1/map endpoint."""
    response = client.get("/api/v1/map")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "adjacency_list" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 57


def test_api_optimize_successful_full_fleet() -> None:
    """Test POST /api/v1/optimize with valid, feasible inputs for 100% bin collection."""
    repo = MapRepository()
    bins = repo.get_nodes_by_type("bin")
    truck_cap = 1500
    max_bins_per_truck = max(1, truck_cap // 400)
    truck_count = math.ceil(len(bins) / max_bins_per_truck) + 5

    payload = {
        "truck_count": truck_count,
        "truck_capacity_kg": truck_cap,
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["is_fallback"] is False
    assert data["uncollected_bins"] == []
    assert data["uncollected_waste_kg"] == 0

    summary = data["summary"]
    assert summary["total_distance_km"] > 0.0
    assert summary["total_waste_collected_kg"] > 0
    assert summary["collection_coverage_pct"] == 100.0
    assert summary["trucks_used"] > 0
    assert summary["execution_time_ms"] >= 0.0
    assert summary["peak_memory_kb"] >= 0.0

    truck_routes = data["truck_routes"]
    assert len(truck_routes) == summary["trucks_used"]
    all_collected_bins = []
    for route in truck_routes:
        assert route["truck_id"].startswith("TRUCK-")
        assert route["collected_weight_kg"] <= truck_cap
        assert route["capacity_utilization_pct"] > 0.0
        assert route["route_distance_km"] > 0.0
        assert route["stop_sequence"][0] == "D0"
        assert route["stop_sequence"][-2] == "T1"
        assert route["stop_sequence"][-1] == "D0"
        assert len(route["full_path_coordinates"]) >= len(route["stop_sequence"])
        for pt in route["full_path_coordinates"]:
            assert "node_id" in pt
            assert "node_type" in pt
            assert "lat" in pt
            assert "lon" in pt
            assert "name" not in pt
        all_collected_bins.extend([s for s in route["stop_sequence"] if s.startswith("B")])

    assert len(all_collected_bins) == len(bins)


def test_api_optimize_capacity_exceeded_fallback_mode() -> None:
    """Test POST /api/v1/optimize when fleet capacity is exceeded.

    Verifies that fallback partial collection engages smoothly without 400 error.
    """
    payload = {
        "truck_count": 5,
        "truck_capacity_kg": 700,
        "allow_partial_collection": True,
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Fallback assertions
    assert data["status"] == "partial_collection"
    assert data["is_fallback"] is True
    assert data["fallback_message"] is not None
    assert len(data["uncollected_bins"]) > 0
    assert data["uncollected_waste_kg"] > 0
    assert data["recommended_fleet_size"] >= 10
    assert data["recommended_truck_capacity_kg"] >= 1000
    assert len(data["warnings"]) >= 1

    summary = data["summary"]
    assert summary["is_fallback"] is True
    assert summary["total_waste_collected_kg"] <= 3500
    assert summary["collection_coverage_pct"] < 100.0
    assert summary["total_waste_available_kg"] > summary["total_waste_collected_kg"]

    # All dispatched trucks must respect the 700 kg capacity limit
    for route in data["truck_routes"]:
        assert route["collected_weight_kg"] <= 700


def test_api_optimize_strict_capacity_exceeded_exception() -> None:
    """Test POST /api/v1/optimize with allow_partial_collection=False raises structured 400 error."""
    payload = {
        "truck_count": 5,
        "truck_capacity_kg": 700,
        "allow_partial_collection": False,
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 400
    data = response.json()

    assert data["status"] == "error"
    assert data["error"] == "CapacityExceeded"
    assert "exceeds total fleet capacity" in data["message"]
    assert data["details"]["total_waste_kg"] > data["details"]["fleet_capacity_kg"]
    assert data["details"]["recommended_truck_count"] >= 10
    assert data["details"]["recommended_truck_capacity_kg"] >= 1000
    assert len(data["suggestions"]) >= 2


def test_api_optimize_overweight_single_bin_fallback() -> None:
    """Test POST /api/v1/optimize when some bins exceed capacity but compliant bins can be serviced."""
    payload = {
        "truck_count": 5,
        "truck_capacity_kg": 350,  # 400kg bins > 350kg will be deferred
        "allow_partial_collection": True,
    }
    response = client.post("/api/v1/optimize", json=payload)
    # Since all bins are 400kg and capacity is 350kg, all bins are overweight -> raises OverweightBinException
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "OverweightBin"


def test_api_optimize_all_bins_overweight_exception() -> None:
    """Test POST /api/v1/optimize when capacity is smaller than the smallest bin (150kg < 400kg)."""
    payload = {
        "truck_count": 10,
        "truck_capacity_kg": 150,
        "allow_partial_collection": True,
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 400
    data = response.json()

    assert data["status"] == "error"
    assert data["error"] == "OverweightBin"
    assert len(data["suggestions"]) > 0


def test_api_optimize_validation_errors() -> None:
    """Test POST /api/v1/optimize validation errors for invalid constraints."""
    # truck_count < 1
    response = client.post("/api/v1/optimize", json={"truck_count": 0, "truck_capacity_kg": 1000})
    assert response.status_code == 422

    # truck_capacity_kg < 100
    response = client.post("/api/v1/optimize", json={"truck_count": 2, "truck_capacity_kg": 50})
    assert response.status_code == 422


def test_api_get_nodes_and_filters() -> None:
    """Test GET /api/v1/nodes with and without type query parameters."""
    response_all = client.get("/api/v1/nodes")
    assert response_all.status_code == 200
    all_nodes = response_all.json()
    assert len(all_nodes) >= 37

    response_bins = client.get("/api/v1/nodes?type=bin")
    assert response_bins.status_code == 200
    bins = response_bins.json()
    assert len(bins) >= 15
    assert all(b["type"] == "bin" for b in bins)


def test_api_get_bins_and_depots() -> None:
    """Test GET /api/v1/bins and GET /api/v1/depots."""
    bins_res = client.get("/api/v1/bins")
    assert bins_res.status_code == 200
    bins = bins_res.json()
    assert len(bins) >= 15

    depots_res = client.get("/api/v1/depots")
    assert depots_res.status_code == 200
    depots = depots_res.json()
    assert len(depots) >= 2
    types = {d["type"] for d in depots}
    assert "start" in types
    assert "destination" in types


def test_api_get_fleet_estimate() -> None:
    """Test GET /api/v1/fleet/estimate."""
    response = client.get("/api/v1/fleet/estimate?truck_capacity_kg=2000")
    assert response.status_code == 200
    data = response.json()
    assert data["total_bins"] >= 15
    assert data["total_waste_kg"] > 0
    assert data["truck_capacity_kg"] == 2000
    assert data["min_trucks_required"] >= 1


# ---------------------------------------------------------
# 6. Advanced Fallback, Validation, and Tiered Dataset Tests
# ---------------------------------------------------------

def test_solve_by_truck_partition_fallback() -> None:
    """Test the direct fallback routing solver with pre-partitioned trucks."""
    dist_matrix = {
        "D0": {"D0": 0.0, "T1": 4.0, "B1": 1.0, "B2": 2.0, "B3": 2.5},
        "T1": {"D0": 4.0, "T1": 0.0, "B1": 3.0, "B2": 2.5, "B3": 1.5},
        "B1": {"D0": 1.0, "T1": 3.0, "B1": 0.0, "B2": 1.2, "B3": 2.0},
        "B2": {"D0": 2.0, "T1": 2.5, "B1": 1.2, "B2": 0.0, "B3": 0.8},
        "B3": {"D0": 2.5, "T1": 1.5, "B1": 2.0, "B2": 0.8, "B3": 0.0},
    }
    truck_partitions = [
        [{"id": "B1", "weight_kg": 400}, {"id": "B2", "weight_kg": 400}],
        [{"id": "B3", "weight_kg": 400}],
    ]

    results, total_dist = solve_by_truck_partition(
        depot_id="D0",
        dump_id="T1",
        truck_partitions=truck_partitions,
        dist_matrix=dist_matrix,
        truck_capacity_kg=1000,
    )

    assert len(results) == 2
    assert results[0].truck_id == "TRUCK-1"
    assert results[0].collected_weight_kg == 800
    assert results[1].truck_id == "TRUCK-2"
    assert results[1].collected_weight_kg == 400
    assert total_dist > 0.0
    for r in results:
        assert r.stop_sequence[0] == "D0"
        assert r.stop_sequence[-2] == "T1"
        assert r.stop_sequence[-1] == "D0"


def test_clarke_wright_iterative_consolidation() -> None:
    """Test that multi-pass consolidation merges small routes when savings list is exhausted."""
    # 4 bins with 200kg each, 2 trucks of 500kg each
    # Distances designed such that savings are minimal, but weights easily fit in 2 trucks
    dist_matrix = {
        "D0": {"D0": 0.0, "T1": 10.0, "B1": 5.0, "B2": 5.0, "B3": 5.0, "B4": 5.0},
        "T1": {"D0": 10.0, "T1": 0.0, "B1": 5.0, "B2": 5.0, "B3": 5.0, "B4": 5.0},
        "B1": {"D0": 5.0, "T1": 5.0, "B1": 0.0, "B2": 9.9, "B3": 9.9, "B4": 9.9},
        "B2": {"D0": 5.0, "T1": 5.0, "B1": 9.9, "B2": 0.0, "B3": 9.9, "B4": 9.9},
        "B3": {"D0": 5.0, "T1": 5.0, "B1": 9.9, "B2": 9.9, "B3": 0.0, "B4": 9.9},
        "B4": {"D0": 5.0, "T1": 5.0, "B1": 9.9, "B2": 9.9, "B3": 9.9, "B4": 0.0},
    }
    bins = [
        {"id": "B1", "weight_kg": 200},
        {"id": "B2", "weight_kg": 200},
        {"id": "B3", "weight_kg": 200},
        {"id": "B4", "weight_kg": 200},
    ]

    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=bins,
        dist_matrix=dist_matrix,
        truck_count=2,
        truck_capacity_kg=500,
        allow_fallback=True,
    )

    assert len(results) <= 2
    total_collected = sum(r.collected_weight_kg for r in results)
    assert total_collected == 800


def test_two_opt_sequence_and_calculate_distance() -> None:
    """Test two_opt_sequence and calculate_route_distance helpers."""
    dist_matrix = {
        "D0": {"D0": 0.0, "T1": 5.0, "B1": 1.0, "B2": 4.0},
        "T1": {"D0": 5.0, "T1": 0.0, "B1": 4.0, "B2": 1.0},
        "B1": {"D0": 1.0, "T1": 4.0, "B1": 0.0, "B2": 1.0},
        "B2": {"D0": 4.0, "T1": 1.0, "B1": 1.0, "B2": 0.0},
    }

    # B2 -> B1 reversed should be worse than B1 -> B2:
    # D0 -> B1 (1) -> B2 (1) -> T1 (1) -> D0 (5) = 8.0
    # D0 -> B2 (4) -> B1 (1) -> T1 (4) -> D0 (5) = 14.0
    seq = ["B2", "B1"]
    opt_seq = two_opt_sequence("D0", "T1", seq, dist_matrix)
    assert opt_seq == ["B1", "B2"]

    dist = calculate_route_distance("D0", "T1", opt_seq, dist_matrix)
    assert abs(dist - 8.0) < 1e-4

    # Empty sequence
    assert two_opt_sequence("D0", "T1", [], dist_matrix) == []
    assert calculate_route_distance("D0", "T1", [], dist_matrix) == 0.0


def test_graph_connectivity_helpers() -> None:
    """Test is_graph_connected and get_connected_components functions."""
    g = nx.Graph()
    assert is_graph_connected(g) is False

    g.add_edge("A", "B", weight=1.0)
    assert is_graph_connected(g) is True
    assert len(get_connected_components(g)) == 1

    g.add_node("C")
    assert is_graph_connected(g) is False
    assert len(get_connected_components(g)) == 2


def test_map_validation_endpoint() -> None:
    """Test GET /api/v1/map/validate endpoint."""
    response = client.get("/api/v1/map/validate")
    assert response.status_code == 200
    data = response.json()

    assert data["is_valid"] is True
    assert data["is_connected"] is True
    assert data["start_depots_count"] >= 1
    assert data["destinations_count"] >= 1
    assert data["smart_bins_count"] >= 15
    assert data["total_nodes"] >= 37
    assert data["total_edges"] >= 42
    assert data["connected_components"] == 1
    assert len(data["validation_messages"]) >= 1


def test_map_reload_endpoint() -> None:
    """Test POST /api/v1/map/reload endpoint with custom datasets and Supabase tiers."""
    # Reload with tier 1 sparse map
    res_tier1 = client.post("/api/v1/map/reload", json={"map_path": "data/city_map_tier1_sparse.json"})
    assert res_tier1.status_code == 200
    data1 = res_tier1.json()
    assert data1["status"] == "success"
    assert data1["bins_loaded"] == 15
    assert "tier1" in data1["map_source"]

    # Verify map endpoint reflects tier 1 dataset
    map_res = client.get("/api/v1/map")
    assert map_res.status_code == 200
    assert len(map_res.json()["nodes"]) == 37

    # Reload with tier 2 medium via explicit tier_id
    res_tier2 = client.post("/api/v1/map/reload", json={"tier_id": "tier2_medium"})
    assert res_tier2.status_code == 200
    data2 = res_tier2.json()
    assert data2["status"] == "success"
    assert data2["bins_loaded"] == 45
    assert "tier2" in data2["map_source"]

    # Reload back to tier 3 dense dataset
    res_dense = client.post("/api/v1/map/reload", json={"tier_id": "tier3_dense"})
    assert res_dense.status_code == 200
    data_dense = res_dense.json()
    assert data_dense["status"] == "success"
    assert data_dense["bins_loaded"] == 120
    assert "tier3" in data_dense["map_source"]

    # Verify map endpoint reflects tier 3 dataset
    map_res_dense = client.get("/api/v1/map")
    assert map_res_dense.status_code == 200
    assert len(map_res_dense.json()["nodes"]) == 182


def test_all_map_tier_datasets() -> None:
    """Test optimization across all 3 map tier datasets."""
    datasets = [
        ("data/city_map_tier1_sparse.json", 15),
        ("data/city_map_tier2_medium.json", 45),
        ("data/city_map_tier3_dense.json", 120),
    ]

    for map_path, expected_bins in datasets:
        settings = Settings(MAP_DATA_PATH=map_path)
        repo = MapRepository(settings=settings)
        service = OptimizerService(map_repo=repo)

        validation = service.validate_map()
        assert validation.is_valid is True
        assert validation.smart_bins_count == expected_bins
        assert validation.is_connected is True

        req = OptimizationRequest(
            truck_count=math.ceil(expected_bins / 3) + 2,
            truck_capacity_kg=1500,
            allow_partial_collection=True,
        )
        response = service.optimize_waste_collection(req)
        assert response.status == "success"
        assert response.summary.collection_coverage_pct == 100.0
        assert response.summary.trucks_used > 0
        assert response.summary.total_distance_km > 0.0
        assert response.summary.execution_time_ms >= 0.0
        assert response.summary.peak_memory_kb >= 0.0


def test_map_repository_resilience_missing_and_corrupted_file() -> None:
    """Test MapRepository fallback behavior for missing or unparseable files."""
    # Non-existent file path: fallback discovery engages
    repo = MapRepository(map_path="data/non_existent_map_12345.json")
    graph = repo.get_graph()
    assert isinstance(graph, nx.Graph)
    assert graph.number_of_nodes() > 0

    # Validation still functions
    val = repo.validate_map_integrity()
    assert val.total_nodes > 0


def test_reconstruct_full_path_edge_cases() -> None:
    """Test reconstruct_full_path with single node, empty list, and identical consecutive stops."""
    repo = MapRepository()
    graph = repo.get_graph()

    assert reconstruct_full_path(graph, []) == []
    assert reconstruct_full_path(graph, ["D0"]) == ["D0"]
    assert reconstruct_full_path(graph, ["D0", "D0"]) == ["D0"]


def test_overweight_single_bin_with_compliant_bins_fallback() -> None:
    """Test fallback when one bin is overweight but compliant bins can be serviced."""
    # Synthetic repository with compliant bins
    settings = Settings(MAP_DATA_PATH="data/city_map_tier1_sparse.json")
    repo = MapRepository(settings=settings)
    service = OptimizerService(map_repo=repo)

    # 400kg bins: with capacity=600kg and truck_count=2, can collect 2 bins (800kg)
    req = OptimizationRequest(
        truck_count=2,
        truck_capacity_kg=600,
        allow_partial_collection=True,
    )
    res = service.optimize_waste_collection(req)
    assert res.status == "partial_collection"
    assert res.is_fallback is True
    assert len(res.uncollected_bins) > 0
    assert len(res.warnings) >= 1
    assert res.summary.total_waste_collected_kg <= 1200


def test_profiler_memory_measurement_and_accuracy() -> None:
    """Test that Profiler measures execution time and dynamic memory accurately."""
    with Profiler() as prof:
        large_list = [i for i in range(200_000)]
        del large_list

    assert prof.execution_time_ms > 0.0
    assert prof.peak_memory_kb >= 0.0


def test_map_repository_nodes_by_type_case_insensitive() -> None:
    """Test that get_nodes_by_type handles case insensitivity and whitespace."""
    repo = MapRepository()
    bins_upper = repo.get_nodes_by_type("BIN")
    bins_lower = repo.get_nodes_by_type("bin  ")
    assert len(bins_upper) == len(bins_lower)
    assert len(bins_upper) >= 15


def test_custom_domain_exceptions_structures() -> None:
    """Test all custom domain exception properties, details, and suggestions."""
    from app.utils.exceptions import (
        InvalidMapDataException,
        MapDataNotFoundException,
        OptimizationException,
        OptimizationTimeoutException,
    )

    base_exc = OptimizationException("Base error", 400, "BaseErr", {"key": "val"}, ["Fix it"])
    assert base_exc.status_code == 400
    assert base_exc.error_type == "BaseErr"
    assert base_exc.details["key"] == "val"
    assert base_exc.suggestions == ["Fix it"]

    map_nf = MapDataNotFoundException("missing.json", ["/path/a", "/path/b"])
    assert map_nf.status_code == 404
    assert map_nf.error_type == "MapDataNotFound"
    assert map_nf.details["configured_path"] == "missing.json"

    inv_map = InvalidMapDataException("corrupt.json", "bad JSON syntax")
    assert inv_map.status_code == 422
    assert inv_map.error_type == "InvalidMapData"

    timeout_exc = OptimizationTimeoutException(1200.5, 1000.0)
    assert timeout_exc.status_code == 504
    assert timeout_exc.error_type == "OptimizationTimeout"


def test_nodes_endpoint_unknown_filter_returns_empty_list() -> None:
    """Test GET /api/v1/nodes?type=unknown returns empty list without error."""
    response = client.get("/api/v1/nodes?type=unknown_type_xyz")
    assert response.status_code == 200
    assert response.json() == []


def test_single_bin_fleet_routing() -> None:
    """Test routing when only 1 bin is present."""
    dist_matrix = {
        "D0": {"D0": 0.0, "T1": 4.0, "B1": 2.0},
        "T1": {"D0": 4.0, "T1": 0.0, "B1": 2.0},
        "B1": {"D0": 2.0, "T1": 2.0, "B1": 0.0},
    }
    bins = [{"id": "B1", "weight_kg": 400}]

    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=bins,
        dist_matrix=dist_matrix,
        truck_count=1,
        truck_capacity_kg=500,
    )

    assert len(results) == 1
    assert results[0].truck_id == "TRUCK-1"
    assert results[0].bins == ["B1"]
    assert results[0].stop_sequence == ["D0", "B1", "T1", "D0"]
    assert results[0].collected_weight_kg == 400
    assert results[0].capacity_utilization_pct == 80.0
    # D0 -> B1 (2.0) + B1 -> T1 (2.0) + T1 -> D0 (4.0) = 8.0
    assert abs(total_dist - 8.0) < 1e-4


# ---------------------------------------------------------
# 7. Additional Edge Case, Exception & Fragmentation Tests
# ---------------------------------------------------------

def test_partition_bins_ffd_decreasing_order() -> None:
    """Verify that FFD prioritizes larger weight items first into trucks."""
    bins = [
        {"id": "B_LIGHT1", "weight_kg": 100},
        {"id": "B_HEAVY", "weight_kg": 900},
        {"id": "B_LIGHT2", "weight_kg": 100},
    ]
    # 1 truck with 950kg capacity: B_HEAVY (900kg) must be placed, leaving B_LIGHT2 uncollected
    truck_partitions, uncollected = partition_bins_ffd(bins, truck_count=1, truck_capacity_kg=950)
    assert len(truck_partitions) == 1
    placed_ids = [b["id"] for b in truck_partitions[0]]
    assert "B_HEAVY" in placed_ids
    assert len(placed_ids) == 1 or sum(b["weight_kg"] for b in truck_partitions[0]) <= 950


def test_api_optimize_fragmentation_fallback() -> None:
    """Test fragmentation fallback when total waste <= total fleet capacity but bin sizing limits truck loading."""
    # Use tier 1 sparse map (15 bins x 400kg = 6000kg)
    # 3 trucks of 2000kg each = 6000kg total capacity
    # Each truck can hold at most 5 bins (5 x 400 = 2000kg)
    # But with 3 trucks and 15 bins, if we configure 3 trucks of 1800kg = 5400kg total capacity
    # (each truck holds 4 bins = 1600kg, so 3 trucks hold 12 bins = 4800kg, deferring 3 bins = 1200kg)
    res_tier1 = client.post("/api/v1/map/reload", json={"map_path": "data/city_map_tier1_sparse.json"})
    assert res_tier1.status_code == 200

    payload = {
        "truck_count": 3,
        "truck_capacity_kg": 1800,
        "allow_partial_collection": True,
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "partial_collection"
    assert data["is_fallback"] is True
    assert len(data["uncollected_bins"]) == 3
    assert data["uncollected_waste_kg"] == 1200
    assert data["summary"]["is_fallback"] is True
    assert data["summary"]["total_waste_collected_kg"] == 4800
    assert data["summary"]["total_waste_available_kg"] == 6000
    assert data["recommended_fleet_size"] is not None
    assert data["recommended_truck_capacity_kg"] is not None
    assert len(data["warnings"]) >= 1

    # Reload back to dense dataset
    client.post("/api/v1/map/reload", json={"map_path": "data/city_map_tier3_dense.json"})


def test_dijkstra_compute_path_matrix() -> None:
    """Test compute_path_matrix helper function."""
    repo = MapRepository()
    graph = repo.get_graph()
    target_nodes = ["D0", "T1", "B1"]

    path_mat = compute_path_matrix(graph, target_nodes)
    assert set(path_mat.keys()) == set(target_nodes)
    for u in target_nodes:
        for v in target_nodes:
            path = path_mat[u][v]
            assert path[0] == u
            assert path[-1] == v

    # Empty target nodes
    assert compute_path_matrix(graph, []) == {}

    # Non-existent node
    with pytest.raises(ValueError, match="Target node 'INVALID' not found"):
        compute_path_matrix(graph, ["INVALID"])


def test_fleet_estimate_validation_error() -> None:
    """Test GET /api/v1/fleet/estimate validation error when truck_capacity_kg < 100."""
    response = client.get("/api/v1/fleet/estimate?truck_capacity_kg=50")
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert data["error"] == "ValidationError"
    assert len(data["suggestions"]) > 0


def test_logger_fallback_zero_total_waste_guard() -> None:
    """Test log_fallback_initiated with 0 total waste does not raise ZeroDivisionError."""
    from app.utils.logger import log_fallback_initiated
    # Should execute cleanly without error
    log_fallback_initiated(
        reason="Test zero waste",
        selected_bins=0,
        total_bins=0,
        collected_weight_kg=0,
        total_waste_kg=0,
        fleet_capacity_kg=1000,
        uncollected_bins_count=0,
    )


def test_get_map_tiers_endpoint() -> None:
    """Test GET /api/v1/map/tiers endpoint returns all available Supabase road network tiers."""
    response = client.get("/api/v1/map/tiers")
    assert response.status_code == 200
    data = response.json()

    assert data["total_tiers"] >= 3
    assert "active_tier_id" in data
    tier_ids = [t["tier_id"] for t in data["tiers"]]
    assert "tier1_sparse" in tier_ids
    assert "tier2_medium" in tier_ids
    assert "tier3_dense" in tier_ids

    active_tier = next(t for t in data["tiers"] if t["tier_id"] == data["active_tier_id"])
    assert active_tier["is_active"] is True
    assert active_tier["node_count"] > 0
    assert active_tier["bin_count"] > 0


