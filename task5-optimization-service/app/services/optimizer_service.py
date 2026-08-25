"""Service orchestrating map data retrieval, graph traversals, fleet optimization, and path reconstruction."""

from typing import Dict, List, Optional
from fastapi import HTTPException, status
import networkx as nx

from app.algorithms.branch_and_bound import solve_fleet_routing
from app.algorithms.dijkstra import compute_distance_matrix, reconstruct_full_path
from app.models.schemas import (
    CityMapResponse,
    CoordinatePoint,
    NodeSchema,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationSummary,
    TruckRouteResponse,
)
from app.repositories.map_repository import MapRepository
from app.utils.logger import (
    log_dijkstra_matrix,
    log_error,
    log_info,
    log_optimization_start,
    log_optimization_summary,
    log_step,
    log_success,
    log_truck_route_details,
    log_warning,
)
from app.utils.profiler import Profiler


class OptimizerService:
    """Core service for city waste collection route planning and fleet optimization."""

    def __init__(self, map_repo: MapRepository) -> None:
        """Initialize the optimizer service with a map repository dependency."""
        self.map_repo = map_repo

    def get_city_map(self) -> CityMapResponse:
        """Retrieve the full city map including all nodes, coordinates, and road edges."""
        full_map = self.map_repo.get_full_map()
        log_info(
            f"GET /api/v1/map -> Returning {len(full_map.nodes)} nodes, "
            f"{len(full_map.edges)} edges, {len(full_map.adjacency_list)} adjacency entries."
        )
        return full_map

    def optimize_waste_collection(self, request: OptimizationRequest) -> OptimizationResponse:
        """Execute the complete waste collection route optimization pipeline.

        1. Validates inputs, map nodes (depot, destination, bins), and capacity constraints.
        2. Verifies road network connectivity.
        3. Measures execution duration and peak memory usage via Profiler.
        4. Precomputes all-pairs shortest distances between POIs using Dijkstra's algorithm.
        5. Solves vehicle partitioning and TSP sequencing with Branch and Bound.
        6. Expands intermediate road intersections for full GPS coordinate trajectories.
        7. Returns structured OptimizationResponse.
        """
        graph = self.map_repo.get_graph()
        nodes_dict = self.map_repo.get_node_dict()

        # 1. Identify start depot, disposal destination, and smart bins
        start_nodes = self.map_repo.get_nodes_by_type("start")
        dest_nodes = self.map_repo.get_nodes_by_type("destination")
        bin_nodes = self.map_repo.get_nodes_by_type("bin")

        if not start_nodes:
            log_error("Map Data Error", "No start depot ('start') node found in city map.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Map data error: No start depot ('start') node found in city map.",
            )
        if not dest_nodes:
            log_error("Map Data Error", "No destination ('destination') node found in city map.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Map data error: No destination ('destination') node found in city map.",
            )

        depot_node = start_nodes[0]
        dump_node = dest_nodes[0]
        total_bin_payload = sum(b.weight_kg for b in bin_nodes)
        total_fleet_capacity = request.truck_count * request.truck_capacity_kg

        # Print visual optimization initiation header
        log_optimization_start(
            truck_count=request.truck_count,
            truck_capacity_kg=request.truck_capacity_kg,
            total_bins=len(bin_nodes),
            total_waste_kg=total_bin_payload,
        )

        # 2. Validate payload capacity constraints
        log_step(
            1, 5, "Validating Fleet Capacity and Payload Constraints",
            {
                "Smart Bins Found": f"{len(bin_nodes)} locations ({total_bin_payload:,} kg total waste)",
                "Fleet Max Capacity": f"{total_fleet_capacity:,} kg ({request.truck_count} trucks x {request.truck_capacity_kg:,} kg)",
                "Start Depot": f"{depot_node.id} ({depot_node.name})",
                "Disposal Facility": f"{dump_node.id} ({dump_node.name})",
            }
        )

        # Check if any individual bin exceeds a single truck's capacity
        overweight_bins = [b for b in bin_nodes if b.weight_kg > request.truck_capacity_kg]
        if overweight_bins:
            bin_details = ", ".join(f"{b.id} ({b.weight_kg}kg)" for b in overweight_bins)
            err_msg = (
                f"Individual bin payload exceeds maximum truck capacity ({request.truck_capacity_kg} kg): "
                f"{bin_details}."
            )
            log_error("Validation Constraint Failed", err_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            )

        # Check if total waste exceeds total fleet capacity
        if total_bin_payload > total_fleet_capacity:
            err_msg = (
                f"Total waste payload ({total_bin_payload} kg) exceeds total fleet capacity "
                f"({total_fleet_capacity} kg = {request.truck_count} trucks × {request.truck_capacity_kg} kg)."
            )
            log_error("Capacity Exceeded", err_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            )

        # 3. Check graph connectivity for all POIs
        poi_ids = [depot_node.id, dump_node.id] + [b.id for b in bin_nodes]
        for poi in poi_ids:
            if poi not in graph:
                err_msg = f"Node '{poi}' is missing from the road network graph."
                log_error("Graph Topology Error", err_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=err_msg,
                )

        # Run optimization within Profiler context
        with Profiler() as profiler:
            try:
                # 4. Precompute distance matrix between POIs using Dijkstra
                log_step(
                    2, 5, "Computing Dijkstra Shortest Road Distance Matrix",
                    {"Points of Interest": f"{len(poi_ids)} key nodes (Depot D0, Dump T1, 25 Bins)"}
                )
                dist_matrix = compute_distance_matrix(graph, poi_ids)
                sample_distances = [
                    (depot_node.id, "B1", dist_matrix[depot_node.id]["B1"]),
                    ("B1", dump_node.id, dist_matrix["B1"][dump_node.id]),
                    (dump_node.id, depot_node.id, dist_matrix[dump_node.id][depot_node.id]),
                ]
                log_dijkstra_matrix(len(poi_ids), sample_distances)
            except ValueError as e:
                log_error("Dijkstra Graph Error", str(e))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Graph connectivity error: {str(e)}",
                )

            # 5. Execute Branch and Bound solver
            log_step(
                3, 5, "Executing Branch and Bound Fleet Route Optimizer",
                {
                    "Algorithm": "Branch & Bound + Held-Karp TSP + Capacity Pruning",
                    "Fleet Partitioning": f"Assigning {len(bin_nodes)} bins across max {request.truck_count} trucks",
                }
            )
            bins_data = [{"id": b.id, "weight_kg": b.weight_kg} for b in bin_nodes]
            try:
                route_results, total_fleet_distance = solve_fleet_routing(
                    depot_id=depot_node.id,
                    dump_id=dump_node.id,
                    bins=bins_data,
                    dist_matrix=dist_matrix,
                    truck_count=request.truck_count,
                    truck_capacity_kg=request.truck_capacity_kg,
                )
            except ValueError as e:
                log_error("Optimization Solving Failed", str(e))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Optimization failed: {str(e)}",
                )

            # 6. Reconstruct full turn-by-turn road intersection paths and map to GPS coordinates
            log_step(
                4, 5, "Reconstructing Turn-by-Turn Road Intersections & GPS Trajectories",
                {"Active Trucks Dispatched": f"{len(route_results)} trucks"}
            )
            truck_route_responses: List[TruckRouteResponse] = []
            for i, res in enumerate(route_results, 1):
                full_path_nodes = reconstruct_full_path(graph, res.stop_sequence)
                coordinates = [
                    CoordinatePoint(
                        node_id=nid,
                        name=nodes_dict[nid].name,
                        node_type=nodes_dict[nid].type,
                        lat=nodes_dict[nid].lat,
                        lon=nodes_dict[nid].lon,
                    )
                    for nid in full_path_nodes
                ]

                log_truck_route_details(
                    truck_id=res.truck_id,
                    truck_num=i,
                    total_trucks=len(route_results),
                    bins=res.bins,
                    collected_weight_kg=res.collected_weight_kg,
                    capacity_kg=request.truck_capacity_kg,
                    utilization_pct=res.capacity_utilization_pct,
                    distance_km=res.route_distance_km,
                    stop_sequence=res.stop_sequence,
                    full_path_nodes=full_path_nodes,
                )

                truck_route_responses.append(
                    TruckRouteResponse(
                        truck_id=res.truck_id,
                        collected_weight_kg=res.collected_weight_kg,
                        capacity_utilization_pct=res.capacity_utilization_pct,
                        route_distance_km=res.route_distance_km,
                        stop_sequence=res.stop_sequence,
                        full_path_coordinates=coordinates,
                    )
                )

        # 7. Construct final summary and response
        log_step(5, 5, "Compiling Metrics & Summary Response")
        summary = OptimizationSummary(
            total_distance_km=total_fleet_distance,
            total_waste_collected_kg=total_bin_payload,
            trucks_used=len(truck_route_responses),
            execution_time_ms=profiler.execution_time_ms,
            peak_memory_kb=profiler.peak_memory_kb,
        )

        log_optimization_summary(
            total_distance_km=total_fleet_distance,
            total_waste_collected_kg=total_bin_payload,
            trucks_used=len(truck_route_responses),
            total_trucks_available=request.truck_count,
            execution_time_ms=profiler.execution_time_ms,
            peak_memory_kb=profiler.peak_memory_kb,
        )

        return OptimizationResponse(
            status="success",
            summary=summary,
            truck_routes=truck_route_responses,
        )

