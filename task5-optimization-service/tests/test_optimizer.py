"""Comprehensive unit and integration test suite for Waste Route Optimization Service."""

import pytest
from fastapi.testclient import TestClient
import networkx as nx

from app.algorithms.branch_and_bound import (
    BranchAndBoundOptimizer,
    select_feasible_bins_ffd,
    solve_fleet_routing,
)
from app.algorithms.dijkstra import (
    compute_distance_matrix,
    compute_shortest_path,
    reconstruct_full_path,
)
from app.main import app
from app.models.schemas import OptimizationRequest
from app.repositories.map_repository import MapRepository
from app.services.optimizer_service import OptimizerService
from app.utils.exceptions import (
    CapacityExceededException,
    OverweightBinException,
)
from app.utils.profiler import Profiler

client = TestClient(app)


# ---------------------------------------------------------
# 1. MapRepository Tests
# ---------------------------------------------------------

def test_map_repository_loads_nodes_and_graph() -> None:
    """Test that MapRepository successfully loads 30 intersections, 25 bins, and builds a connected NetworkX graph."""
    repo = MapRepository()
    graph = repo.get_graph()

    assert isinstance(graph, nx.Graph)
    assert graph.number_of_nodes() == 57  # 1 Depot + 1 Dump + 30 Intersections + 25 Bins
    assert graph.number_of_edges() >= 57
    assert nx.is_connected(graph)

    # Check start depot
    start_nodes = repo.get_nodes_by_type("start")
    assert len(start_nodes) == 1
    assert start_nodes[0].id == "D0"
    assert start_nodes[0].weight_kg == 0

    # Check destination station
    dest_nodes = repo.get_nodes_by_type("destination")
    assert len(dest_nodes) == 1
    assert dest_nodes[0].id == "T1"
    assert dest_nodes[0].weight_kg == 0

    # Check intersections
    intersections = repo.get_nodes_by_type("intersection")
    assert len(intersections) == 30
    for inter in intersections:
        assert inter.weight_kg == 0

    # Check smart bins
    bins = repo.get_nodes_by_type("bin")
    assert len(bins) == 25
    for b in bins:
        assert b.weight_kg >= 200
        assert b.weight_kg <= 500


def test_map_repository_node_dict_and_lookup() -> None:
    """Test node dictionary retrieval and single node lookup."""
    repo = MapRepository()
    nodes_dict = repo.get_node_dict()

    assert "D0" in nodes_dict
    assert "T1" in nodes_dict
    assert "B1" in nodes_dict
    assert "I30" in nodes_dict

    d0 = repo.get_node("D0")
    assert d0.name == "Central Municipal Depot"

    with pytest.raises(KeyError):
        repo.get_node("NON_EXISTENT_NODE")


def test_map_repository_full_map_response() -> None:
    """Test that full map response contains nodes and adjacency list."""
    repo = MapRepository()
    full_map = repo.get_full_map()

    assert len(full_map.nodes) == 57
    assert len(full_map.adjacency_list) == 57
    assert len(full_map.edges) >= 57


# ---------------------------------------------------------
# 2. Dijkstra Algorithm & Path Reconstruction Tests
# ---------------------------------------------------------

def test_dijkstra_distance_matrix() -> None:
    """Test computation of all-pairs shortest road distance matrix."""
    repo = MapRepository()
    graph = repo.get_graph()

    target_nodes = ["D0", "T1", "B1", "B2", "B25"]
    dist_matrix = compute_distance_matrix(graph, target_nodes)

    assert len(dist_matrix) == len(target_nodes)
    for u in target_nodes:
        assert dist_matrix[u][u] == 0.0
        for v in target_nodes:
            assert dist_matrix[u][v] > 0.0 or u == v
            assert pytest.approx(dist_matrix[u][v], rel=1e-3) == dist_matrix[v][u]


def test_dijkstra_reconstruct_full_path() -> None:
    """Test expanding high-level stops into full turn-by-turn intersection sequences."""
    repo = MapRepository()
    graph = repo.get_graph()

    stop_sequence = ["D0", "B1"]
    full_path = reconstruct_full_path(graph, stop_sequence)

    assert full_path[0] == "D0"
    assert full_path[-1] == "B1"
    # Should include intermediate road network junctions
    assert len(full_path) >= 2

    # Multi-leg stop sequence: D0 -> B1 -> T1 -> D0
    cycle_sequence = ["D0", "B1", "T1", "D0"]
    full_cycle = reconstruct_full_path(graph, cycle_sequence)

    assert full_cycle[0] == "D0"
    assert full_cycle[-1] == "D0"
    assert "B1" in full_cycle
    assert "T1" in full_cycle
    # Verify no consecutive identical nodes
    for i in range(len(full_cycle) - 1):
        assert full_cycle[i] != full_cycle[i + 1]


def test_dijkstra_disconnected_error() -> None:
    """Test that disconnected nodes or invalid nodes raise appropriate errors."""
    disconnected_graph = nx.Graph()
    disconnected_graph.add_node("A")
    disconnected_graph.add_node("B")

    with pytest.raises(ValueError, match="No navigable road path exists"):
        compute_distance_matrix(disconnected_graph, ["A", "B"])

    with pytest.raises(ValueError, match="Target node 'Z' not found"):
        compute_distance_matrix(disconnected_graph, ["Z"])


# ---------------------------------------------------------
# 3. Branch and Bound & FFD Packing Algorithm Tests
# ---------------------------------------------------------

def test_select_feasible_bins_ffd() -> None:
    """Test First-Fit Decreasing bin selection heuristic."""
    bins = [
        {"id": "B1", "weight_kg": 400},
        {"id": "B2", "weight_kg": 350},
        {"id": "B3", "weight_kg": 300},
        {"id": "B4", "weight_kg": 250},
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


def test_branch_and_bound_subset_truck() -> None:
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


def test_branch_and_bound_multi_truck_partitioning() -> None:
    """Test that all 25 bins are partitioned correctly across trucks respecting capacity constraints."""
    repo = MapRepository()
    graph = repo.get_graph()
    bins = repo.get_nodes_by_type("bin")

    poi_ids = ["D0", "T1"] + [b.id for b in bins]
    dist_matrix = compute_distance_matrix(graph, poi_ids)
    bins_data = [{"id": b.id, "weight_kg": b.weight_kg} for b in bins]

    # Capacity = 1500kg per truck, 25 bins (~8500-9630kg) -> requires ~6-8 trucks
    results, total_dist = solve_fleet_routing(
        depot_id="D0",
        dump_id="T1",
        bins=bins_data,
        dist_matrix=dist_matrix,
        truck_count=8,
        truck_capacity_kg=1500,
    )

    assert len(results) >= 5
    all_collected_bins = []
    for res in results:
        assert res.collected_weight_kg <= 1500
        assert res.stop_sequence[0] == "D0"
        assert res.stop_sequence[-2] == "T1"
        assert res.stop_sequence[-1] == "D0"
        all_collected_bins.extend(res.bins)

    # All 25 bins must be collected exactly once
    assert sorted(all_collected_bins) == sorted([b.id for b in bins])


def test_branch_and_bound_empty_bins() -> None:
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
    assert len(data["nodes"]) == 57


def test_api_optimize_successful_full_fleet() -> None:
    """Test POST /api/v1/optimize with valid, feasible inputs for 100% bin collection."""
    payload = {
        "truck_count": 8,
        "truck_capacity_kg": 1500,
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
        assert route["collected_weight_kg"] <= 1500
        assert route["capacity_utilization_pct"] > 0.0
        assert route["route_distance_km"] > 0.0
        assert route["stop_sequence"][0] == "D0"
        assert route["stop_sequence"][-2] == "T1"
        assert route["stop_sequence"][-1] == "D0"
        assert len(route["full_path_coordinates"]) >= len(route["stop_sequence"])
        all_collected_bins.extend([s for s in route["stop_sequence"] if s.startswith("B")])

    assert len(all_collected_bins) == 25


def test_api_optimize_capacity_exceeded_fallback_mode() -> None:
    """Test POST /api/v1/optimize when fleet capacity is exceeded (10 trucks x 700 kg = 7000 kg < 9630 kg).

    Verifies that fallback partial collection engages smoothly without 400 error.
    """
    payload = {
        "truck_count": 10,
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
    assert data["recommended_fleet_size"] >= 14
    assert data["recommended_truck_capacity_kg"] >= 963
    assert len(data["warnings"]) >= 1

    summary = data["summary"]
    assert summary["is_fallback"] is True
    assert summary["total_waste_collected_kg"] <= 7000
    assert summary["collection_coverage_pct"] < 100.0
    assert summary["total_waste_available_kg"] > summary["total_waste_collected_kg"]

    # All dispatched trucks must respect the 700 kg capacity limit
    for route in data["truck_routes"]:
        assert route["collected_weight_kg"] <= 700


def test_api_optimize_strict_capacity_exceeded_exception() -> None:
    """Test POST /api/v1/optimize with allow_partial_collection=False raises structured 400 error."""
    payload = {
        "truck_count": 10,
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
    assert data["details"]["recommended_truck_count"] >= 14
    assert data["details"]["recommended_truck_capacity_kg"] >= 963
    assert len(data["suggestions"]) >= 2


def test_api_optimize_overweight_single_bin_fallback() -> None:
    """Test POST /api/v1/optimize when some bins exceed capacity but compliant bins can be serviced."""
    payload = {
        "truck_count": 5,
        "truck_capacity_kg": 350,  # Bins > 350kg will be deferred
        "allow_partial_collection": True,
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_fallback"] is True
    assert len(data["uncollected_bins"]) > 0
    for route in data["truck_routes"]:
        assert route["collected_weight_kg"] <= 350


def test_api_optimize_all_bins_overweight_exception() -> None:
    """Test POST /api/v1/optimize when capacity is smaller than the smallest bin (150kg < 200kg min)."""
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
