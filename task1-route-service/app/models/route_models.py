"""Pydantic request and response models for Route Optimization."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class CityModel(BaseModel):
    """City vertex representation."""

    id: str
    name: str
    latitude: float
    longitude: float
    x: Optional[float] = None
    y: Optional[float] = None
    kind: str = "city"
    connections: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoadModel(BaseModel):
    """Road edge representation."""

    source: str
    destination: str
    distance_km: float
    travel_time_min: Optional[float] = None
    is_bidirectional: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkResponse(BaseModel):
    """Full city network topology."""

    cities: list[CityModel]
    roads: list[RoadModel]
    total_cities: int
    total_roads: int


class RouteRequest(BaseModel):
    """Payload to find route between two locations."""

    start: str = Field(..., description="Starting city ID or location key")
    destination: str = Field(..., description="Destination city ID or location key")
    algorithm: Literal["bfs", "dijkstra", "astar"] = Field(
        default="astar", description="Pathfinding algorithm to execute"
    )


class RouteResponse(BaseModel):
    """Response payload for a single path calculation."""

    algorithm: str
    start: str
    destination: str
    route: list[str] = Field(
        ..., description="Ordered list of location IDs from start to destination"
    )
    route_names: list[str] = Field(
        ..., description="Ordered list of human-readable city names"
    )
    distance: float = Field(..., description="Total route distance in km")
    nodes_explored: int = Field(
        ..., description="Number of vertices expanded during search"
    )
    execution_time_ms: float = Field(
        ..., description="Actual measured algorithm wall-clock time in milliseconds"
    )
    is_optimal_distance: bool = Field(
        ..., description="Whether this algorithm guarantees optimal shortest distance"
    )
    hops: int = Field(..., description="Number of road edges in path")
    notes: str = Field(
        default="", description="Theoretical explanation of algorithm behavior"
    )


class ComparisonRequest(BaseModel):
    """Payload to compare all algorithms on the same route."""

    start: str
    destination: str


class ComparisonResponse(BaseModel):
    """Comparative performance report for BFS, Dijkstra, and A*."""

    start: str
    destination: str
    results: list[RouteResponse]
    analysis: str


class BenchmarkTierResult(BaseModel):
    """Benchmark performance metrics for a specific network size."""

    tier_name: str
    node_count: int
    edge_count: int
    bfs_time_ms: float
    bfs_nodes: int
    dijkstra_time_ms: float
    dijkstra_nodes: int
    astar_time_ms: float
    astar_nodes: int


class BenchmarkResponse(BaseModel):
    """Result of systematic performance experiments across graph sizes."""

    runs_averaged: int
    tiers: list[BenchmarkTierResult]
    conclusion: str
