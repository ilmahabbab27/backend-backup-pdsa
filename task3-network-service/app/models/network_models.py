"""Database-facing models for city locations and roads."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# T3DS: City location entity representing a graph node or transport stop in the road network.
class Location(BaseModel):
    """A city location or intersection represented as a graph node."""

    id: UUID
    location_key: str
    name: str
    type: str
    latitude: float | None = None
    longitude: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# T3DS: Road record used to connect two location nodes; it may be directional or bidirectional.
class Road(BaseModel):
    """A road represented as a directed or bidirectional graph edge."""

    id: UUID
    from_location_key: str
    to_location_key: str
    distance_km: float
    travel_time_min: float | None = None
    is_bidirectional: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# T3DS: Lightweight DTO used by the UI to populate the selectable list of start nodes.
class AvailableNode(BaseModel):
    """A lightweight location that can be selected for analysis."""

    location_key: str
    name: str
    type: str


class AvailableNodesResponse(BaseModel):
    """The locations available as traversal starting nodes."""

    nodes: list[AvailableNode]


# T3DS: Returned traversal result with ordered visit sequence and measured runtime in milliseconds.
class TraversalResult(BaseModel):
    """Traversal output and measured algorithm execution time."""

    traversal_order: list[str]
    visited_count: int
    execution_time_ms: float


# T3DS: Centrality score for one node, including degree count and normalized network importance.
class CentralityResult(BaseModel):
    """A ranked location and its degree metrics."""

    location_key: str
    name: str
    degree: int
    centrality: float
    rank: int


# T3DS: Summary wrapper for the single most connected node in the analyzed graph.
class MostConnectedLocation(BaseModel):
    """Summary of the highest-ranked location."""

    location_key: str
    name: str
    degree: int
    centrality: float


# T3DS: Full network diagnostic payload including BFS, DFS, centrality, and connectivity summary.
class NetworkAnalysisResponse(BaseModel):
    """Complete Task 3 analysis for a selected starting location."""

    start_node: str
    start_location_name: str
    total_nodes: int
    total_edges: int
    reachable_nodes: int
    unreachable_nodes: int
    reachability_percentage: float
    connectivity_status: Literal["fully_connected", "partially_connected", "isolated"]
    most_connected_location: MostConnectedLocation | None
    network_density: float
    bfs: TraversalResult
    dfs: TraversalResult
    centrality: list[CentralityResult]
    metrics_execution_time_ms: float
    total_execution_time_ms: float
