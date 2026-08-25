"""Repository for loading, caching, and serving city map and road network graph data."""

import json
from pathlib import Path
from typing import Dict, List, Optional
import networkx as nx

from app.config.settings import Settings, get_settings
from app.models.schemas import CityMapResponse, EdgeSchema, NodeSchema


class MapRepository:
    """Repository managing city map data and NetworkX road network graph construction."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the map repository with application settings."""
        self._settings = settings or get_settings()
        self._raw_data: Optional[dict] = None
        self._graph: Optional[nx.Graph] = None
        self._nodes_dict: Optional[Dict[str, NodeSchema]] = None
        self._full_map_response: Optional[CityMapResponse] = None
        self._load_and_build()

    def _load_and_build(self) -> None:
        """Load JSON file from disk and build NetworkX graph along with cached data structures."""
        file_path = self._settings.resolved_map_data_path
        if not file_path.exists():
            raise FileNotFoundError(
                f"City map data file not found at '{file_path}'. Please ensure 'data/city_map.json' exists."
            )

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._raw_data = data
        nodes_raw = data.get("nodes", [])
        adj_raw = data.get("adjacency_list", {})

        # Parse nodes into NodeSchema and build dictionary
        nodes_dict: Dict[str, NodeSchema] = {}
        nodes_list: List[NodeSchema] = []
        for n in nodes_raw:
            node = NodeSchema(
                id=n["id"],
                type=n["type"],
                name=n["name"],
                lat=float(n["lat"]),
                lon=float(n["lon"]),
                weight_kg=int(n.get("weight_kg", 0)),
            )
            nodes_dict[node.id] = node
            nodes_list.append(node)
        self._nodes_dict = nodes_dict

        # Build NetworkX undirected graph
        graph = nx.Graph()
        for node in nodes_list:
            graph.add_node(
                node.id,
                type=node.type,
                name=node.name,
                lat=node.lat,
                lon=node.lon,
                weight_kg=node.weight_kg,
            )

        # Build edges from adjacency list (deduplicating undirected edges)
        edges_list: List[EdgeSchema] = []
        seen_edges = set()
        for source_id, neighbors in adj_raw.items():
            for nbr in neighbors:
                target_id = nbr["target"]
                distance_km = float(nbr["distance_km"])
                graph.add_edge(source_id, target_id, weight=distance_km)

                edge_key = tuple(sorted([source_id, target_id]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges_list.append(
                        EdgeSchema(
                            source=edge_key[0],
                            target=edge_key[1],
                            distance_km=distance_km,
                        )
                    )

        self._graph = graph
        self._full_map_response = CityMapResponse(
            nodes=nodes_list,
            adjacency_list=adj_raw,
            edges=edges_list,
        )
        total_waste = sum(n.weight_kg for n in nodes_list if n.type == "bin")
        from app.utils.logger import log_info
        log_info(
            f"MapRepository loaded {len(nodes_list)} nodes ({len([n for n in nodes_list if n.type == 'bin'])} bins, {total_waste:,} kg waste), "
            f"{len(edges_list)} edges from '{file_path.name}'"
        )

    def get_graph(self) -> nx.Graph:
        """Return the constructed NetworkX Graph."""
        if self._graph is None:
            self._load_and_build()
        return self._graph  # type: ignore[return-value]

    def get_full_map(self) -> CityMapResponse:
        """Return the complete CityMapResponse schema containing all nodes and adjacency structures."""
        if self._full_map_response is None:
            self._load_and_build()
        return self._full_map_response  # type: ignore[return-value]

    def get_nodes_by_type(self, node_type: str) -> List[NodeSchema]:
        """Return all nodes matching a given type (e.g., 'start', 'destination', 'intersection', 'bin')."""
        if self._nodes_dict is None:
            self._load_and_build()
        return [node for node in self._nodes_dict.values() if node.type == node_type]  # type: ignore[union-attr]

    def get_node_dict(self) -> Dict[str, NodeSchema]:
        """Return a mapping of node IDs to NodeSchema objects."""
        if self._nodes_dict is None:
            self._load_and_build()
        return self._nodes_dict  # type: ignore[return-value]

    def get_node(self, node_id: str) -> NodeSchema:
        """Get a single node by its ID. Raises KeyError if not found."""
        if self._nodes_dict is None:
            self._load_and_build()
        if node_id not in self._nodes_dict:  # type: ignore[operator]
            raise KeyError(f"Node '{node_id}' not found in map repository.")
        return self._nodes_dict[node_id]  # type: ignore[index]

    def reload(self) -> None:
        """Force reloads map data from the file system."""
        self._load_and_build()
