"""Graph data structures using adjacency-list representation for sparse road networks."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Node:
    """Represents a city/location vertex in the transportation network."""

    id: str
    name: str
    latitude: float
    longitude: float
    x: Optional[float] = None
    y: Optional[float] = None
    kind: str = "city"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Represents a road/connection between two cities."""

    source: str
    destination: str
    distance_km: float
    travel_time_min: Optional[float] = None
    is_bidirectional: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class Graph:
    """Adjacency-list graph representation of a weighted transportation network.

    Adjacency lists are chosen over adjacency matrices because city road
    networks are sparse (where |E| is typically O(|V|)). This yields O(|V| + |E|)
    space efficiency and O(deg(V)) neighbor iteration time.
    """

    def __init__(self, is_directed: bool = False) -> None:
        self.is_directed = is_directed
        self.nodes: dict[str, Node] = {}
        # Adjacency list: mapping node_id -> list of (neighbor_id, distance_km)
        self.adj: dict[str, list[tuple[str, float]]] = {}
        self.edges_list: list[Edge] = []

    def add_node(
        self,
        node_id: str,
        name: str,
        latitude: float,
        longitude: float,
        x: Optional[float] = None,
        y: Optional[float] = None,
        kind: str = "city",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Node:
        """Add a city vertex to the network."""
        node = Node(
            id=node_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            x=x,
            y=y,
            kind=kind,
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        if node_id not in self.adj:
            self.adj[node_id] = []
        return node

    def add_edge(
        self,
        source: str,
        destination: str,
        distance_km: float,
        travel_time_min: Optional[float] = None,
        is_bidirectional: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a weighted edge between two cities.

        By default, adds an undirected road (bidirectional).
        """
        if source not in self.adj:
            self.adj[source] = []
        if destination not in self.adj:
            self.adj[destination] = []

        # Avoid duplicate edges
        self.adj[source].append((destination, distance_km))
        if is_bidirectional and not self.is_directed:
            self.adj[destination].append((source, distance_km))

        edge = Edge(
            source=source,
            destination=destination,
            distance_km=distance_km,
            travel_time_min=travel_time_min,
            is_bidirectional=is_bidirectional,
            metadata=metadata or {},
        )
        self.edges_list.append(edge)

    def get_neighbors(self, node_id: str) -> list[tuple[str, float]]:
        """Return list of (neighbor_id, distance_km) for a node."""
        return self.adj.get(node_id, [])

    def has_node(self, node_id: str) -> bool:
        """Check if a city node exists in the graph."""
        return node_id in self.nodes

    def get_node(self, node_id: str) -> Optional[Node]:
        """Retrieve node object by id."""
        return self.nodes.get(node_id)

    @property
    def vertex_count(self) -> int:
        """Number of vertices in graph."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Number of unique road segments."""
        return len(self.edges_list)
