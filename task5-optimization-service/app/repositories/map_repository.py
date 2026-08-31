"""Repository for loading, caching, and serving city map and road network graph data."""

import json
from pathlib import Path
from typing import Dict, List, Optional
import networkx as nx

from app.algorithms.dijkstra import get_connected_components, is_graph_connected
from app.config.settings import Settings, get_settings
from app.models.schemas import (
    CityMapResponse,
    EdgeSchema,
    MapValidationResponse,
    NodeSchema,
)
from app.utils.exceptions import InvalidMapDataException, MapDataNotFoundException
from app.utils.logger import log_error, log_info, log_warning


class MapRepository:
    """Repository managing city map data and NetworkX road network graph construction."""

    def __init__(self, settings: Optional[Settings] = None, map_path: Optional[str] = None) -> None:
        """Initialize the map repository with application settings or custom map path."""
        self._settings = settings or get_settings()
        self._custom_map_path: Optional[str] = map_path
        self._loaded_path: Optional[Path] = None
        self._raw_data: Optional[dict] = None
        self._graph: Optional[nx.Graph] = None
        self._nodes_dict: Optional[Dict[str, NodeSchema]] = None
        self._full_map_response: Optional[CityMapResponse] = None
        self._load_and_build()

    @property
    def loaded_path(self) -> Path:
        """Return the resolved path of the currently loaded map file."""
        return self._loaded_path or self._settings.resolved_map_data_path

    def _resolve_file_path(self) -> Path:
        """Resolve map file path with automated fallback discovery if configured path is missing."""
        if self._custom_map_path:
            p = Path(self._custom_map_path)
            if not p.is_absolute():
                p = (self._settings.BASE_DIR / p).resolve()
            if p.exists():
                return p

        configured_path = self._settings.resolved_map_data_path
        if configured_path.exists():
            return configured_path

        # Candidate fallback map locations
        search_candidates = [
            self._settings.BASE_DIR / "data" / "city_map.json",
            self._settings.BASE_DIR / "data" / "city_map_tier3_dense.json",
            self._settings.BASE_DIR / "data" / "city_map_tier2_medium.json",
            self._settings.BASE_DIR / "data" / "city_map_tier1_sparse.json",
            Path("data/city_map.json").resolve(),
        ]

        for cand in search_candidates:
            if cand.exists():
                log_warning(f"Configured map '{configured_path}' not found. Falling back to '{cand.name}'.")
                return cand.resolve()

        return configured_path

    def _generate_synthetic_fallback_map(self) -> dict:
        """Generate a minimal connected default map topology when no map files exist on disk."""
        log_warning("No map JSON files found on disk. Initializing emergency synthetic default map.")
        return {
            "nodes": [
                {"id": "D0", "type": "start", "name": "Default Central Municipal Depot", "lat": 40.7580, "lon": -73.9995, "weight_kg": 0},
                {"id": "T1", "type": "destination", "name": "Default Waste Disposal Facility", "lat": 40.7180, "lon": -73.9750, "weight_kg": 0},
                {"id": "I1", "type": "intersection", "name": "Default Central Junction 1", "lat": 40.7500, "lon": -73.9850, "weight_kg": 0},
                {"id": "B1", "type": "bin", "name": "Default Smart Bin 1", "lat": 40.7400, "lon": -73.9800, "weight_kg": 400},
                {"id": "B2", "type": "bin", "name": "Default Smart Bin 2", "lat": 40.7300, "lon": -73.9900, "weight_kg": 400},
            ],
            "adjacency_list": {
                "D0": [{"target": "I1", "distance_km": 1.2}],
                "I1": [{"target": "D0", "distance_km": 1.2}, {"target": "B1", "distance_km": 1.5}, {"target": "B2", "distance_km": 1.8}, {"target": "T1", "distance_km": 2.0}],
                "B1": [{"target": "I1", "distance_km": 1.5}, {"target": "B2", "distance_km": 0.8}, {"target": "T1", "distance_km": 1.4}],
                "B2": [{"target": "I1", "distance_km": 1.8}, {"target": "B1", "distance_km": 0.8}, {"target": "T1", "distance_km": 1.6}],
                "T1": [{"target": "I1", "distance_km": 2.0}, {"target": "B1", "distance_km": 1.4}, {"target": "B2", "distance_km": 1.6}],
            },
        }

    def _load_and_build(self) -> None:
        """Load JSON file from disk and build NetworkX graph along with cached data structures."""
        file_path = self._resolve_file_path()
        data: Optional[dict] = None

        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                log_error("Map Parsing Error", f"Failed to parse JSON map file at '{file_path}': {e}")
                data = self._generate_synthetic_fallback_map()
        else:
            data = self._generate_synthetic_fallback_map()

        if not isinstance(data, dict):
            data = self._generate_synthetic_fallback_map()

        self._loaded_path = file_path
        self._raw_data = data
        nodes_raw = data.get("nodes", [])
        adj_raw = data.get("adjacency_list", {})

        # Parse nodes into NodeSchema and build dictionary
        nodes_dict: Dict[str, NodeSchema] = {}
        nodes_list: List[NodeSchema] = []
        for n in nodes_raw:
            try:
                node = NodeSchema(
                    id=str(n.get("id", "")).strip(),
                    type=n.get("type", "intersection"),
                    name=n.get("name", f"Node {n.get('id', '')}"),
                    lat=float(n.get("lat", 0.0)),
                    lon=float(n.get("lon", 0.0)),
                    weight_kg=int(n.get("weight_kg", 0)),
                )
                if node.id:
                    nodes_dict[node.id] = node
                    nodes_list.append(node)
            except Exception as e:
                log_warning(f"Skipping malformed node entry {n}: {e}")

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
            if not isinstance(neighbors, list):
                continue
            # Ensure source_id exists in nodes_dict
            if source_id not in nodes_dict:
                synthetic_src = NodeSchema(
                    id=source_id,
                    type="intersection",
                    name=f"Intersection {source_id}",
                    lat=0.0,
                    lon=0.0,
                    weight_kg=0,
                )
                nodes_dict[source_id] = synthetic_src
                nodes_list.append(synthetic_src)
                graph.add_node(source_id, type="intersection", name=synthetic_src.name, lat=0.0, lon=0.0, weight_kg=0)

            for nbr in neighbors:
                if not isinstance(nbr, dict):
                    continue
                target_id = str(nbr.get("target", "")).strip()
                if not target_id:
                    continue
                try:
                    distance_km = max(0.001, float(nbr.get("distance_km", 1.0)))
                except (ValueError, TypeError):
                    distance_km = 1.0

                # Ensure target_id exists in nodes_dict
                if target_id not in nodes_dict:
                    synthetic_tgt = NodeSchema(
                        id=target_id,
                        type="intersection",
                        name=f"Intersection {target_id}",
                        lat=0.0,
                        lon=0.0,
                        weight_kg=0,
                    )
                    nodes_dict[target_id] = synthetic_tgt
                    nodes_list.append(synthetic_tgt)
                    graph.add_node(target_id, type="intersection", name=synthetic_tgt.name, lat=0.0, lon=0.0, weight_kg=0)

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

        self._nodes_dict = nodes_dict
        self._graph = graph
        self._full_map_response = CityMapResponse(
            nodes=nodes_list,
            adjacency_list=adj_raw,
            edges=edges_list,
        )

        total_waste = sum(n.weight_kg for n in nodes_list if n.type == "bin")
        bin_count = len([n for n in nodes_list if n.type == "bin"])
        log_info(
            f"MapRepository loaded {len(nodes_list)} nodes ({bin_count} bins, {total_waste:,} kg waste), "
            f"{len(edges_list)} edges from '{file_path.name if file_path else 'synthetic'}'"
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
        target_type = node_type.lower().strip()
        return [node for node in self._nodes_dict.values() if node.type.lower() == target_type]  # type: ignore[union-attr]

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

    def reload(self, custom_path: Optional[str] = None) -> None:
        """Force reloads map data from the file system or switches to a custom dataset."""
        if custom_path is not None:
            self._custom_map_path = custom_path
        self._load_and_build()

    def validate_map_integrity(self) -> MapValidationResponse:
        """Evaluate road network graph integrity, connectivity, depot/dump presence, and metrics."""
        graph = self.get_graph()
        nodes_dict = self.get_node_dict()

        start_nodes = self.get_nodes_by_type("start")
        dest_nodes = self.get_nodes_by_type("destination")
        bin_nodes = self.get_nodes_by_type("bin")
        intersection_nodes = self.get_nodes_by_type("intersection")

        total_waste = sum(b.weight_kg for b in bin_nodes)
        components = get_connected_components(graph)
        is_connected = is_graph_connected(graph)

        messages: List[str] = []
        is_valid = True

        if not start_nodes:
            is_valid = False
            messages.append("CRITICAL: No start depot ('start') node found.")
        if not dest_nodes:
            is_valid = False
            messages.append("CRITICAL: No waste disposal facility ('destination') node found.")
        if not bin_nodes:
            messages.append("WARNING: No smart bins found in road network.")
        if not is_connected:
            is_valid = False
            messages.append(
                f"CRITICAL: Graph is disconnected into {len(components)} separate components. "
                "Ensure all roads have navigable connections."
            )
        else:
            messages.append("SUCCESS: Road network graph is fully connected and navigable.")

        return MapValidationResponse(
            is_valid=is_valid,
            map_source=str(self.loaded_path),
            total_nodes=len(nodes_dict),
            start_depots_count=len(start_nodes),
            destinations_count=len(dest_nodes),
            smart_bins_count=len(bin_nodes),
            intersections_count=len(intersection_nodes),
            total_edges=graph.number_of_edges(),
            total_waste_kg=total_waste,
            is_connected=is_connected,
            connected_components=len(components),
            validation_messages=messages,
        )

