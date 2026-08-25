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

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Graph topology error: {detail}",
            status_code=400,
            error_type="GraphTopologyError",
            suggestions=[
                "Verify that city map JSON contains both depot ('start') and dump ('destination') nodes.",
                "Ensure all road segments are properly connected in the adjacency list.",
            ],
        )
