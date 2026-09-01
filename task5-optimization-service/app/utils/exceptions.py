"""Custom exception classes for waste collection routing and fleet optimization."""

import math
from typing import Any, Dict, List, Optional


class OptimizationException(Exception):
    """Base exception class for all optimization service errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_type: str = "OptimizationError",
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details or {}
        self.suggestions = suggestions or []


class CapacityExceededException(OptimizationException):
    """Raised when total waste payload exceeds total available fleet capacity and fallback is disabled."""

    def __init__(
        self,
        total_waste_kg: int,
        fleet_capacity_kg: int,
        truck_count: int,
        truck_capacity_kg: int,
        allow_partial_collection: bool = False,
    ) -> None:
        deficit_kg = total_waste_kg - fleet_capacity_kg
        recommended_truck_count = math.ceil(total_waste_kg / truck_capacity_kg) if truck_capacity_kg > 0 else truck_count
        recommended_truck_capacity = math.ceil(total_waste_kg / truck_count) if truck_count > 0 else truck_capacity_kg

        message = (
            f"Total waste payload ({total_waste_kg:,} kg) exceeds total fleet capacity "
            f"({fleet_capacity_kg:,} kg = {truck_count} trucks × {truck_capacity_kg:,} kg). "
            f"Capacity deficit: {deficit_kg:,} kg."
        )

        suggestions = [
            f"Increase fleet size to at least {recommended_truck_count} trucks (with {truck_capacity_kg:,} kg capacity each).",
            f"Increase individual truck capacity to at least {recommended_truck_capacity:,} kg (with {truck_count} trucks).",
            "Enable partial collection fallback ('allow_partial_collection': true) to prioritize high-yield bins within available capacity.",
        ]

        details = {
            "total_waste_kg": total_waste_kg,
            "fleet_capacity_kg": fleet_capacity_kg,
            "capacity_deficit_kg": deficit_kg,
            "truck_count": truck_count,
            "truck_capacity_kg": truck_capacity_kg,
            "recommended_truck_count": recommended_truck_count,
            "recommended_truck_capacity_kg": recommended_truck_capacity,
            "allow_partial_collection": allow_partial_collection,
        }

        super().__init__(
            message=message,
            status_code=400,
            error_type="CapacityExceeded",
            details=details,
            suggestions=suggestions,
        )


class OverweightBinException(OptimizationException):
    """Raised when individual bins exceed single truck capacity and cannot be collected."""

    def __init__(
        self,
        overweight_bins: List[Dict[str, Any]],
        truck_capacity_kg: int,
    ) -> None:
        bin_strs = [f"{b['id']} ({b['weight_kg']:,} kg)" for b in overweight_bins]
        max_bin_weight = max(b["weight_kg"] for b in overweight_bins) if overweight_bins else truck_capacity_kg
        message = (
            f"Individual bin payload exceeds maximum truck capacity ({truck_capacity_kg:,} kg): "
            f"{', '.join(bin_strs)}."
        )

        suggestions = [
            f"Increase truck capacity to at least {max_bin_weight:,} kg to accommodate the heaviest bin.",
            "Enable partial collection fallback to service compliant bins while deferring overweight bins for specialized handling.",
        ]

        details = {
            "truck_capacity_kg": truck_capacity_kg,
            "overweight_bins": overweight_bins,
            "max_bin_weight_kg": max_bin_weight,
        }

        super().__init__(
            message=message,
            status_code=400,
            error_type="OverweightBin",
            details=details,
            suggestions=suggestions,
        )


class InfeasibleRoutingException(OptimizationException):
    """Raised when no feasible route or vehicle partitioning could be constructed."""

    def __init__(self, detail: str, suggestions: Optional[List[str]] = None) -> None:
        super().__init__(
            message=f"No feasible fleet route allocation found: {detail}",
            status_code=400,
            error_type="InfeasibleRouting",
            suggestions=suggestions
            or [
                "Increase the number of available trucks to reduce bin packing fragmentation.",
                "Increase truck payload capacity.",
                "Verify that all bins and depots have navigable road connections.",
            ],
        )


class GraphTopologyException(OptimizationException):
    """Raised when map topology is invalid or disconnected."""

    def __init__(self, detail: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=f"Graph topology error: {detail}",
            status_code=400,
            error_type="GraphTopologyError",
            details=details or {"error_detail": detail},
            suggestions=[
                "Verify that city map JSON contains both depot ('start') and dump ('destination') nodes.",
                "Ensure all road segments are properly connected in the adjacency list without isolated subgraphs.",
                "Check that all node IDs referenced in adjacency list are properly declared.",
            ],
        )


class MapDataNotFoundException(OptimizationException):
    """Raised when map data file cannot be found at configured path and fallbacks fail."""

    def __init__(self, path: str, searched_paths: Optional[List[str]] = None) -> None:
        super().__init__(
            message=f"City map data file not found at '{path}'.",
            status_code=404,
            error_type="MapDataNotFound",
            details={"configured_path": path, "searched_paths": searched_paths or []},
            suggestions=[
                "Ensure map files exist in 'data/' (e.g., 'data/city_map_tier1_sparse.json', 'data/city_map_tier2_medium.json', 'data/city_map_tier3_dense.json').",
                "Check MAP_DATA_PATH in your .env configuration.",
                "Use the /api/v1/map/reload endpoint to reload with an available dataset.",
            ],
        )


class InvalidMapDataException(OptimizationException):
    """Raised when map data file exists but is corrupted, unparseable, or missing key schema structures."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            message=f"City map data at '{path}' is invalid or corrupted: {reason}",
            status_code=422,
            error_type="InvalidMapData",
            details={"file_path": path, "reason": reason},
            suggestions=[
                "Verify that the map file contains valid JSON with 'nodes' and 'adjacency_list' keys.",
                "Ensure each node has 'id', 'type', 'lat', and 'lon' fields.",
            ],
        )


class OptimizationTimeoutException(OptimizationException):
    """Raised when optimization exceeds execution time SLA limits."""

    def __init__(self, elapsed_ms: float, limit_ms: float) -> None:
        super().__init__(
            message=f"Optimization exceeded time limit of {limit_ms:.1f} ms (took {elapsed_ms:.1f} ms).",
            status_code=504,
            error_type="OptimizationTimeout",
            details={"elapsed_ms": elapsed_ms, "limit_ms": limit_ms},
            suggestions=[
                "Reduce the number of bins scheduled in a single optimization dispatch.",
                "Increase the time limit configuration.",
            ],
        )

