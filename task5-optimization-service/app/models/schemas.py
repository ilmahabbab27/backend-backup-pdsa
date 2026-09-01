"""Pydantic schemas for data validation and API response serialization."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class NodeSchema(BaseModel):
    """Schema representing a road network node."""

    id: str = Field(..., description="Unique node identifier, e.g., 'D0', 'T1', 'I1', 'B1'")
    type: Literal["start", "destination", "intersection", "bin"] = Field(
        ..., description="Type of node: depot start, destination, intersection, or smart bin"
    )
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
    allow_partial_collection: bool = Field(
        True,
        description=(
            "When true (default), enables fallback to collect the maximum feasible waste within fleet capacity "
            "limits rather than raising a capacity exceeded error."
        ),
    )


class CoordinatePoint(BaseModel):
    """Detailed GPS waypoint in a vehicle's full travel path."""

    node_id: str = Field(..., description="Node identifier")
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
        ..., ge=0, description="Total waste collected across scheduled smart bins in kilograms"
    )
    total_waste_available_kg: int = Field(
        ..., ge=0, description="Total waste weight across all city smart bins in kilograms"
    )
    collection_coverage_pct: float = Field(
        100.0, ge=0.0, le=100.0, description="Percentage of available city waste collected in this run"
    )
    trucks_used: int = Field(..., ge=0, description="Number of trucks actively dispatched")
    total_trucks_available: int = Field(..., ge=1, description="Total trucks configured in fleet")
    is_fallback: bool = Field(False, description="True if capacity fallback was activated")
    execution_time_ms: float = Field(
        ..., ge=0.0, description="Total optimization calculation time in milliseconds"
    )
    peak_memory_kb: float = Field(
        ..., ge=0.0, description="Peak dynamic heap memory allocation in kilobytes"
    )


class OptimizationResponse(BaseModel):
    """Complete response returned by the optimization service."""

    status: str = Field(
        "success",
        description="Status indicator: 'success' (100% collected) or 'partial_collection' (capacity fallback)",
    )
    is_fallback: bool = Field(False, description="Whether fallback mode was triggered")
    fallback_message: Optional[str] = Field(None, description="Diagnostic message when fallback is triggered")
    summary: OptimizationSummary = Field(..., description="Summary metrics of the solution")
    truck_routes: List[TruckRouteResponse] = Field(
        ..., description="Optimized route details for each dispatched truck"
    )
    uncollected_bins: List[str] = Field(
        default_factory=list, description="IDs of smart bins deferred due to capacity constraints"
    )
    uncollected_waste_kg: int = Field(0, description="Total waste kg deferred due to capacity constraints")
    recommended_fleet_size: Optional[int] = Field(
        None, description="Recommended minimum fleet size to collect 100% of city waste"
    )
    recommended_truck_capacity_kg: Optional[int] = Field(
        None, description="Recommended minimum capacity per truck to collect 100% of city waste"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Operational warnings or constraint fallback notes"
    )


class StructuredErrorResponse(BaseModel):
    """Standardized structured error response payload."""

    status: str = Field("error", description="Error status indicator")
    error: str = Field(..., description="High-level error classification")
    message: str = Field(..., description="Descriptive error explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic context")
    suggestions: List[str] = Field(default_factory=list, description="Actionable recommendations to resolve the issue")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field("ok", description="Service health status")
    service: str = Field("task5-optimization-service", description="Service name")
    timestamp: str = Field(..., description="ISO 8601 current timestamp")


class FleetEstimateResponse(BaseModel):
    """Estimation of fleet requirements for city waste collection."""

    total_bins: int = Field(..., description="Total number of smart bins in the city")
    total_waste_kg: int = Field(..., description="Total waste weight across all smart bins in kilograms")
    truck_capacity_kg: int = Field(..., description="Uniform capacity per truck in kilograms")
    min_trucks_required: int = Field(..., description="Theoretical minimum trucks needed to collect all waste")


class MapValidationResponse(BaseModel):
    """Integrity and topology validation report for the road network graph."""

    is_valid: bool = Field(..., description="Whether the road network graph is valid and connected")
    map_source: str = Field(..., description="Source path of the currently loaded map JSON")
    total_nodes: int = Field(..., description="Total count of road network nodes")
    start_depots_count: int = Field(..., description="Count of start depots (D0)")
    destinations_count: int = Field(..., description="Count of disposal facilities (T1)")
    smart_bins_count: int = Field(..., description="Count of smart waste bins")
    intersections_count: int = Field(..., description="Count of road junctions")
    total_edges: int = Field(..., description="Total count of bidirectional road edges")
    total_waste_kg: int = Field(..., description="Total waste weight across all smart bins")
    is_connected: bool = Field(..., description="Whether the road network graph is fully connected")
    connected_components: int = Field(1, description="Number of connected graph components")
    validation_messages: List[str] = Field(default_factory=list, description="Diagnostic notices or warnings")


class MapReloadRequest(BaseModel):
    """Request payload to dynamically reload or switch the city map dataset."""

    tier_id: Optional[str] = Field(
        None,
        description="Supabase map tier ID (e.g. 'tier1_sparse', 'tier2_medium', 'tier3_dense')",
    )
    map_path: Optional[str] = Field(
        None,
        description="Optional relative or absolute path (or tier name) to switch dataset",
    )


class MapReloadResponse(BaseModel):
    """Response after reloading city map dataset."""

    status: str = Field("success", description="Status of the reload operation")
    map_source: str = Field(..., description="Resolved source identifier of the newly loaded map dataset")
    nodes_loaded: int = Field(..., description="Number of nodes loaded")
    bins_loaded: int = Field(..., description="Number of smart bins loaded")
    edges_loaded: int = Field(..., description="Number of road edges constructed")
    total_waste_kg: int = Field(..., description="Total waste weight in loaded dataset")
    timestamp: str = Field(..., description="ISO 8601 reload timestamp")


class MapTierSummary(BaseModel):
    """Metadata summary of an individual road network tier in Supabase."""

    tier_id: str = Field(..., description="Unique tier ID (e.g., 'tier1_sparse', 'tier2_medium', 'tier3_dense')")
    tier_level: int = Field(..., description="Tier complexity level (1, 2, or 3)")
    display_name: str = Field(..., description="Human-readable title of the map tier")
    description: Optional[str] = Field(None, description="Detailed description of network topology")
    node_count: int = Field(..., description="Total nodes in the graph")
    bin_count: int = Field(..., description="Total smart collection bins")
    intersection_count: int = Field(..., description="Total road intersections")
    edge_count: int = Field(..., description="Total undirected road segments")
    total_waste_kg: float = Field(..., description="Total aggregate waste capacity in kg")
    is_active: bool = Field(False, description="True if this tier is currently loaded in memory")


class MapTiersResponse(BaseModel):
    """Response containing all available road network tiers in Supabase."""

    active_tier_id: str = Field(..., description="Currently active map tier identifier")
    total_tiers: int = Field(..., description="Total number of map tiers available")
    tiers: List[MapTierSummary] = Field(..., description="List of all available map tiers")


