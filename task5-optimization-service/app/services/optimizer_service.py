"""Service orchestrating map data retrieval, graph traversals, fleet optimization, and path reconstruction."""

import math
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
import networkx as nx

from app.algorithms.branch_and_bound import select_feasible_bins_ffd, solve_fleet_routing
from app.algorithms.dijkstra import compute_distance_matrix, reconstruct_full_path
from app.models.schemas import (
    CityMapResponse,
    CoordinatePoint,
    FleetEstimateResponse,
    NodeSchema,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationSummary,
    TruckRouteResponse,
)
from app.repositories.map_repository import MapRepository
from app.utils.exceptions import (
    CapacityExceededException,
    GraphTopologyException,
    InfeasibleRoutingException,
    OverweightBinException,
)
from app.utils.logger import (
    log_dijkstra_matrix,
    log_error,
    log_fallback_initiated,
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

    def get_nodes(self, node_type: Optional[str] = None) -> List[NodeSchema]:
        """Retrieve all nodes or filter by node type ('start', 'destination', 'intersection', 'bin')."""
        if node_type:
            nodes = self.map_repo.get_nodes_by_type(node_type.lower().strip())
            log_info(f"GET /api/v1/nodes?type={node_type} -> Returning {len(nodes)} nodes.")
            return nodes
        nodes = list(self.map_repo.get_node_dict().values())
        log_info(f"GET /api/v1/nodes -> Returning {len(nodes)} nodes.")
        return nodes

    def get_bins(self) -> List[NodeSchema]:
        """Retrieve all smart waste collection bins."""
        bins = self.map_repo.get_nodes_by_type("bin")
        log_info(f"GET /api/v1/bins -> Returning {len(bins)} smart bins.")
        return bins

    def get_depots(self) -> List[NodeSchema]:
        """Retrieve start depot and waste disposal facility nodes."""
        depots = self.map_repo.get_nodes_by_type("start") + self.map_repo.get_nodes_by_type("destination")
        log_info(f"GET /api/v1/depots -> Returning {len(depots)} facility nodes.")
        return depots

    def get_fleet_estimate(self, truck_capacity_kg: int = 1500) -> FleetEstimateResponse:
        """Estimate fleet requirements for collecting all city waste given a truck capacity."""
        bins = self.map_repo.get_nodes_by_type("bin")
        total_waste_kg = sum(b.weight_kg for b in bins)
        min_trucks_required = math.ceil(total_waste_kg / truck_capacity_kg) if truck_capacity_kg > 0 else 0
        log_info(
            f"GET /api/v1/fleet/estimate?truck_capacity_kg={truck_capacity_kg} -> "
            f"{len(bins)} bins, {total_waste_kg} kg waste, min {min_trucks_required} trucks."
        )
        return FleetEstimateResponse(
            total_bins=len(bins),
            total_waste_kg=total_waste_kg,
            truck_capacity_kg=truck_capacity_kg,
            min_trucks_required=min_trucks_required,
        )


    def optimize_waste_collection(self, request: OptimizationRequest) -> OptimizationResponse:
        """Execute the complete waste collection route optimization pipeline.

        1. Validates inputs, map nodes (depot, destination, bins), and capacity constraints.
        2. Evaluates fleet capacity against total payload. If capacity is exceeded:
           - In fallback mode (`allow_partial_collection=True`): Prioritizes and packs the maximal
             feasible subset of smart bins using First-Fit Decreasing heuristic.
           - In strict mode (`allow_partial_collection=False`): Raises `CapacityExceededException`.
        3. Verifies road network connectivity.
        4. Precomputes all-pairs shortest distances between POIs using Dijkstra's algorithm.
        5. Solves vehicle partitioning and TSP sequencing with Branch and Bound.
        6. Expands intermediate road intersections for full GPS coordinate trajectories.
        7. Returns structured OptimizationResponse with fallback metadata, warnings, and fleet recommendations.
        """
        graph = self.map_repo.get_graph()
        nodes_dict = self.map_repo.get_node_dict()

        # 1. Identify start depot, disposal destination, and smart bins
        start_nodes = self.map_repo.get_nodes_by_type("start")
        dest_nodes = self.map_repo.get_nodes_by_type("destination")
        bin_nodes = self.map_repo.get_nodes_by_type("bin")

        if not start_nodes:
            log_error("Map Data Error", "No start depot ('start') node found in city map.")
            raise GraphTopologyException("No start depot ('start') node found in city map.")
        if not dest_nodes:
            log_error("Map Data Error", "No destination ('destination') node found in city map.")
            raise GraphTopologyException("No destination ('destination') node found in city map.")

        depot_node = start_nodes[0]
        dump_node = dest_nodes[0]
        total_bin_payload = sum(b.weight_kg for b in bin_nodes)
        total_fleet_capacity = request.truck_count * request.truck_capacity_kg
        recommended_fleet_size = math.ceil(total_bin_payload / request.truck_capacity_kg) if request.truck_capacity_kg > 0 else request.truck_count
        recommended_truck_capacity_kg = math.ceil(total_bin_payload / request.truck_count) if request.truck_count > 0 else request.truck_capacity_kg

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
                "Partial Fallback Allowed": "Enabled" if request.allow_partial_collection else "Disabled (Strict)",
            }
        )

        # Check for overweight bins exceeding single truck capacity
        overweight_bins = [b for b in bin_nodes if b.weight_kg > request.truck_capacity_kg]
        is_capacity_exceeded = total_bin_payload > total_fleet_capacity
        is_fallback = False
        fallback_message: Optional[str] = None
        warnings: List[str] = []
        uncollected_bin_ids: List[str] = []
        uncollected_waste_kg: int = 0
        scheduled_bins_data: List[Dict[str, Any]] = []

        all_bins_data = [{"id": b.id, "weight_kg": b.weight_kg} for b in bin_nodes]

        # Handling capacity exceeded and overweight bins
        if overweight_bins or is_capacity_exceeded:
            if not request.allow_partial_collection:
                # Strict mode: Raise exceptions with structured diagnostic metadata
                if overweight_bins:
                    err_bins = [{"id": b.id, "weight_kg": b.weight_kg} for b in overweight_bins]
                    log_error(
                        "Validation Constraint Failed: Overweight Bin",
                        f"{len(overweight_bins)} bins exceed truck capacity ({request.truck_capacity_kg:,} kg).",
                        [f"Increase truck capacity to at least {max(b.weight_kg for b in overweight_bins):,} kg."]
                    )
                    raise OverweightBinException(err_bins, request.truck_capacity_kg)

                err_msg = (
                    f"Total waste payload ({total_bin_payload:,} kg) exceeds total fleet capacity "
                    f"({total_fleet_capacity:,} kg = {request.truck_count} trucks × {request.truck_capacity_kg:,} kg)."
                )
                log_error("Capacity Exceeded", err_msg, [
                    f"Increase truck count to at least {recommended_fleet_size} trucks.",
                    f"Increase truck capacity to at least {recommended_truck_capacity_kg:,} kg.",
                    "Enable partial collection fallback ('allow_partial_collection': true).",
                ])
                raise CapacityExceededException(
                    total_waste_kg=total_bin_payload,
                    fleet_capacity_kg=total_fleet_capacity,
                    truck_count=request.truck_count,
                    truck_capacity_kg=request.truck_capacity_kg,
                    allow_partial_collection=False,
                )

            # Fallback mode: Select maximal feasible subset using First-Fit Decreasing bin packing
            packed_bins, uncollected_bins = select_feasible_bins_ffd(
                bins=all_bins_data,
                truck_count=request.truck_count,
                truck_capacity_kg=request.truck_capacity_kg,
            )

            if not packed_bins:
                log_error(
                    "Capacity Fallback Exhausted",
                    f"No smart bins could be collected within truck capacity ({request.truck_capacity_kg:,} kg).",
                )
                raise OverweightBinException(
                    overweight_bins=[{"id": b.id, "weight_kg": b.weight_kg} for b in overweight_bins],
                    truck_capacity_kg=request.truck_capacity_kg,
                )

            is_fallback = True
            scheduled_bins_data = packed_bins
            uncollected_bin_ids = [b["id"] for b in uncollected_bins]
            uncollected_waste_kg = sum(int(b["weight_kg"]) for b in uncollected_bins)
            collected_payload = sum(int(b["weight_kg"]) for b in packed_bins)
            coverage_pct = round((collected_payload / total_bin_payload) * 100.0, 1)

            trigger_reason = (
                f"Total waste payload ({total_bin_payload:,} kg) exceeds fleet capacity ({total_fleet_capacity:,} kg)"
                if is_capacity_exceeded
                else f"{len(overweight_bins)} bins exceed single truck capacity ({request.truck_capacity_kg:,} kg)"
            )

            fallback_message = (
                f"Fleet capacity constraint triggered fallback: Prioritized {len(packed_bins)} of {len(bin_nodes)} smart bins "
                f"({collected_payload:,} kg, {coverage_pct}% coverage). Deferred {len(uncollected_bin_ids)} bins "
                f"({uncollected_waste_kg:,} kg) to next collection dispatch."
            )

            warnings.append(fallback_message)
            if overweight_bins:
                warnings.append(
                    f"{len(overweight_bins)} overweight bins ({', '.join(b.id for b in overweight_bins)}) "
                    f"exceed single truck capacity ({request.truck_capacity_kg:,} kg) and were excluded from this fleet."
                )
            warnings.append(
                f"Recommended fleet adjustment: Minimum {recommended_fleet_size} trucks of {request.truck_capacity_kg:,} kg, "
                f"or minimum {recommended_truck_capacity_kg:,} kg capacity for {request.truck_count} trucks for 100% coverage."
            )

            log_fallback_initiated(
                reason=trigger_reason,
                selected_bins=len(packed_bins),
                total_bins=len(bin_nodes),
                collected_weight_kg=collected_payload,
                total_waste_kg=total_bin_payload,
                fleet_capacity_kg=total_fleet_capacity,
                uncollected_bins_count=len(uncollected_bin_ids),
            )
        else:
            scheduled_bins_data = all_bins_data

        # 3. Check graph connectivity for all scheduled POIs
        poi_ids = [depot_node.id, dump_node.id] + [b["id"] for b in scheduled_bins_data]
        for poi in poi_ids:
            if poi not in graph:
                err_msg = f"Node '{poi}' is missing from the road network graph."
                log_error("Graph Topology Error", err_msg)
                raise GraphTopologyException(err_msg)

        # Run optimization within Profiler context
        with Profiler() as profiler:
            # 4. Precompute distance matrix between POIs using Dijkstra
            try:
                log_step(
                    2, 5, "Computing Dijkstra Shortest Road Distance Matrix",
                    {"Points of Interest": f"{len(poi_ids)} key nodes (Depot D0, Dump T1, {len(scheduled_bins_data)} Bins)"}
                )
                dist_matrix = compute_distance_matrix(graph, poi_ids)
                sample_distances = [
                    (depot_node.id, poi_ids[2], dist_matrix[depot_node.id][poi_ids[2]]) if len(poi_ids) > 2 else (depot_node.id, dump_node.id, dist_matrix[depot_node.id][dump_node.id]),
                    (poi_ids[2], dump_node.id, dist_matrix[poi_ids[2]][dump_node.id]) if len(poi_ids) > 2 else (dump_node.id, depot_node.id, dist_matrix[dump_node.id][depot_node.id]),
                    (dump_node.id, depot_node.id, dist_matrix[dump_node.id][depot_node.id]),
                ]
                log_dijkstra_matrix(len(poi_ids), sample_distances)
            except ValueError as e:
                log_error("Dijkstra Graph Error", str(e))
                raise GraphTopologyException(str(e))

            # 5. Execute Branch and Bound solver
            log_step(
                3, 5, "Executing Branch and Bound Fleet Route Optimizer",
                {
                    "Algorithm": "Branch & Bound + Held-Karp TSP + Capacity Pruning",
                    "Fleet Partitioning": f"Assigning {len(scheduled_bins_data)} bins across max {request.truck_count} trucks",
                    "Mode": "Capacity Fallback Subset" if is_fallback else "Full Collection",
                }
            )
            try:
                route_results, total_fleet_distance = solve_fleet_routing(
                    depot_id=depot_node.id,
                    dump_id=dump_node.id,
                    bins=scheduled_bins_data,
                    dist_matrix=dist_matrix,
                    truck_count=request.truck_count,
                    truck_capacity_kg=request.truck_capacity_kg,
                )
            except ValueError as e:
                # If B&B fails on the subset, attempt one more emergency heuristic partition fallback
                if request.allow_partial_collection:
                    log_warning(f"B&B Partitioning infeasible ({e}). Engaging secondary bin packing heuristic fallback.")
                    packed_bins_2, uncollected_bins_2 = select_feasible_bins_ffd(
                        bins=scheduled_bins_data,
                        truck_count=request.truck_count,
                        truck_capacity_kg=request.truck_capacity_kg,
                    )
                    if packed_bins_2 and len(packed_bins_2) < len(scheduled_bins_data):
                        poi_ids_2 = [depot_node.id, dump_node.id] + [b["id"] for b in packed_bins_2]
                        dist_matrix_2 = compute_distance_matrix(graph, poi_ids_2)
                        route_results, total_fleet_distance = solve_fleet_routing(
                            depot_id=depot_node.id,
                            dump_id=dump_node.id,
                            bins=packed_bins_2,
                            dist_matrix=dist_matrix_2,
                            truck_count=request.truck_count,
                            truck_capacity_kg=request.truck_capacity_kg,
                        )
                        is_fallback = True
                        uncollected_bin_ids.extend([b["id"] for b in uncollected_bins_2])
                        uncollected_waste_kg += sum(int(b["weight_kg"]) for b in uncollected_bins_2)
                    else:
                        log_error("Optimization Solving Failed", str(e))
                        raise InfeasibleRoutingException(str(e))
                else:
                    log_error("Optimization Solving Failed", str(e))
                    raise InfeasibleRoutingException(str(e))

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
        total_collected_weight = sum(r.collected_weight_kg for r in truck_route_responses)
        coverage_pct = round((total_collected_weight / total_bin_payload) * 100.0, 2) if total_bin_payload > 0 else 100.0

        log_step(5, 5, "Compiling Metrics & Summary Response")
        summary = OptimizationSummary(
            total_distance_km=total_fleet_distance,
            total_waste_collected_kg=total_collected_weight,
            total_waste_available_kg=total_bin_payload,
            collection_coverage_pct=coverage_pct,
            trucks_used=len(truck_route_responses),
            total_trucks_available=request.truck_count,
            is_fallback=is_fallback,
            execution_time_ms=profiler.execution_time_ms,
            peak_memory_kb=profiler.peak_memory_kb,
        )

        log_optimization_summary(
            total_distance_km=total_fleet_distance,
            total_waste_collected_kg=total_collected_weight,
            total_waste_available_kg=total_bin_payload,
            trucks_used=len(truck_route_responses),
            total_trucks_available=request.truck_count,
            execution_time_ms=profiler.execution_time_ms,
            peak_memory_kb=profiler.peak_memory_kb,
            is_fallback=is_fallback,
            uncollected_count=len(uncollected_bin_ids),
        )

        return OptimizationResponse(
            status="partial_collection" if is_fallback else "success",
            is_fallback=is_fallback,
            fallback_message=fallback_message,
            summary=summary,
            truck_routes=truck_route_responses,
            uncollected_bins=uncollected_bin_ids,
            uncollected_waste_kg=uncollected_waste_kg,
            recommended_fleet_size=recommended_fleet_size if (is_fallback or is_capacity_exceeded) else None,
            recommended_truck_capacity_kg=recommended_truck_capacity_kg if (is_fallback or is_capacity_exceeded) else None,
            warnings=warnings,
        )
