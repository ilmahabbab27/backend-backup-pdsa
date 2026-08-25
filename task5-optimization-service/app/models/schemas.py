"""Pydantic schemas for data validation and API response serialization."""

from typing import Any, Dict, List, Literal
from pydantic import BaseModel, ConfigDict, Field


class NodeSchema(BaseModel):
    """Schema representing a road network node."""

    id: str = Field(..., description="Unique node identifier, e.g., 'D0', 'T1', 'I1', 'B1'")
    type: Literal["start", "destination", "intersection", "bin"] = Field(
        ..., description="Type of node: depot start, destination, intersection, or smart bin"
    )
    name: str = Field(..., description="Human-readable location name")
    lat: float = Field(..., description="GPS Latitude coordinate")
    lon: float = Field(..., description="GPS Longitude coordinate")
    weight_kg: int = Field(
        0, ge=0, description="Waste payload weight in kg (>0 for bins, 0 for depot/intersections/destination)"
    )

    model_config = ConfigDict(from_attributes=True)


class EdgeNeighbor(BaseModel):
    """Neighbor connection in the adjacency list."""

    target: str = Field(..., description="Target node ID")
    distance_km: float = Field(..., gt=0, description="Road segment distance in kilometers")


class EdgeSchema(BaseModel):
    """Flat representation of a graph road edge."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    distance_km: float = Field(..., gt=0, description="Road segment distance in kilometers")


class CityMapResponse(BaseModel):
    """Response containing the entire city map structure and road network."""

    nodes: List[NodeSchema] = Field(..., description="List of all nodes in the road network")
    adjacency_list: Dict[str, List[Dict[str, Any]]] = Field(
        ..., description="Adjacency list mapping node IDs to neighboring nodes and road distances"
    )
    edges: List[EdgeSchema] = Field(
        default_factory=list, description="Flat list of unique undirected road edges for graph visualization"
    )


class OptimizationRequest(BaseModel):
    """Request payload for fleet route optimization."""

    truck_count: int = Field(
        ..., ge=1, description="Number of homogeneous collection trucks available in the fleet"
    )
    truck_capacity_kg: int = Field(
        ..., ge=100, description="Uniform maximum payload capacity per truck in kilograms"
    )


class CoordinatePoint(BaseModel):
    """Detailed GPS waypoint in a vehicle's full travel path."""

    node_id: str = Field(..., description="Node identifier")
    name: str = Field(..., description="Location name")
    node_type: str = Field(..., description="Node classification type")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class TruckRouteResponse(BaseModel):
    """Detailed route, sequence, and metrics for a single dispatched truck."""

    truck_id: str = Field(..., description="Truck unique identifier (e.g., 'TRUCK-1')")
    collected_weight_kg: int = Field(
        ..., ge=0, description="Total waste weight collected by this truck in kilograms"
    )
    capacity_utilization_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Capacity utilization percentage (collected / capacity * 100)"
    )
    route_distance_km: float = Field(
        ..., ge=0.0, description="Total road distance traversed by this truck in kilometers"
    )
    stop_sequence: List[str] = Field(
        ..., description="High-level sequence of key stops: [D0, B_..., T1, D0]"
    )
    full_path_coordinates: List[CoordinatePoint] = Field(
        ..., description="Complete turn-by-turn road network waypoints including intermediate intersections"
    )


class OptimizationSummary(BaseModel):
    """Aggregated metrics across the entire collection fleet."""

    total_distance_km: float = Field(
        ..., ge=0.0, description="Cumulative road distance traversed by all trucks in kilometers"
    )
    total_waste_collected_kg: int = Field(
        ..., ge=0, description="Total waste collected across all smart bins in kilograms"
    )
    trucks_used: int = Field(..., ge=0, description="Number of trucks actively dispatched")
    execution_time_ms: float = Field(
        ..., ge=0.0, description="Total optimization calculation time in milliseconds"
    )
    peak_memory_kb: float = Field(
        ..., ge=0.0, description="Peak dynamic heap memory allocation in kilobytes"
    )


class OptimizationResponse(BaseModel):
    """Complete response returned by the optimization service."""

    status: str = Field("success", description="Status indicator of the optimization outcome")
    summary: OptimizationSummary = Field(..., description="Summary metrics of the solution")
    truck_routes: List[TruckRouteResponse] = Field(
        ..., description="Optimized route details for each dispatched truck"
    )


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field("ok", description="Service health status")
    service: str = Field("task5-optimization-service", description="Service name")
    timestamp: str = Field(..., description="ISO 8601 current timestamp")
