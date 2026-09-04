"""Common type definitions and result structures for graph search algorithms."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AlgorithmResult:
    """Represents the outcome of a pathfinding algorithm run."""

    algorithm: str
    start: str
    destination: str
    path: list[str]
    distance_km: float
    nodes_explored: int
    execution_time_ms: float
    is_optimal_distance: bool
    notes: str
    explored_sequence: Optional[list[str]] = None

    @property
    def hops(self) -> int:
        """Number of road segments in the computed path."""
        return max(0, len(self.path) - 1)
