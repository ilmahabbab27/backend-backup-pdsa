"""Repository for loading, caching, and serving city map and road network graph data from Supabase."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import networkx as nx

from app.algorithms.dijkstra import get_connected_components, is_graph_connected
from app.config.settings import Settings, get_settings
from app.models.schemas import (
    CityMapResponse,
    EdgeSchema,
    MapTierSummary,
    MapValidationResponse,
    NodeSchema,
)
from app.utils.exceptions import InvalidMapDataException, MapDataNotFoundException
from app.utils.logger import log_error, log_info, log_warning


class MapRepository:
    """Repository managing city map data and NetworkX road network graph construction from Supabase."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        map_path: Optional[str] = None,
        tier_id: Optional[str] = None,
    ) -> None:
        """Initialize the map repository with application settings, Supabase tier ID, or custom map path."""
        self._settings = settings or get_settings()
        self._custom_map_path: Optional[str] = map_path
        self._custom_tier_id: Optional[str] = tier_id
        self._current_tier_id: str = "tier3_dense"
        self._loaded_source: str = ""
        self._loaded_path: Optional[Path] = None
        self._raw_data: Optional[dict] = None
        self._graph: Optional[nx.Graph] = None
        self._nodes_dict: Optional[Dict[str, NodeSchema]] = None
        self._full_map_response: Optional[CityMapResponse] = None
        self._load_and_build()

    @property
    def current_tier_id(self) -> str:
        """Return the identifier of the active map tier (e.g., 'tier1_sparse', 'tier2_medium', 'tier3_dense')."""
        return self._current_tier_id

    @property
    def loaded_path(self) -> Path:
        """Return the resolved path or identifier of the currently loaded map dataset."""
        return self._loaded_path or self._settings.resolved_map_data_path

    @property
    def loaded_source(self) -> str:
        """Return human-readable source of the loaded map data (e.g. 'supabase:tier2_medium' or file path)."""
        return self._loaded_source or str(self.loaded_path)

    def _resolve_target_tier(self) -> str:
        """Resolve the target Supabase tier ID from explicit tier_id, custom map path, or configuration."""
        if self._custom_tier_id:
            return Settings.resolve_tier_id_from_path(self._custom_tier_id)
        if self._custom_map_path:
            return Settings.resolve_tier_id_from_path(self._custom_map_path)
        if self._settings.MAP_DATA_PATH and any(t in str(self._settings.MAP_DATA_PATH).lower() for t in ["tier1", "tier2", "tier3", "sparse", "medium", "dense"]):
            return Settings.resolve_tier_id_from_path(self._settings.MAP_DATA_PATH)
        if self._settings.SUPABASE_MAP_TIER:
            return Settings.resolve_tier_id_from_path(self._settings.SUPABASE_MAP_TIER)
        return "tier3_dense"

    def _load_from_supabase(self, tier_id: str) -> Optional[dict]:
        """Attempt to load the specified map tier directly from the Supabase database."""
        url = self._settings.SUPABASE_URL
        key = self._settings.SUPABASE_KEY
        if not url or not key:
            return None

        try:
            from app.utils.supabase_map_seeder import get_supabase_client, resolve_table_name
            client = get_supabase_client(url, key)
            target_table = resolve_table_name(client, "task5_city_maps")
            res = client.table(target_table).select("*").eq("tier_id", tier_id).single().execute()
            if res.data and "nodes" in res.data and "adjacency_list" in res.data:
                log_info(
                    f"Loaded map '{tier_id}' directly from Supabase table '{target_table}' "
                    f"({res.data.get('node_count')} nodes, {res.data.get('bin_count')} bins)."
                )
                return {
                    "nodes": res.data["nodes"],
                    "adjacency_list": res.data["adjacency_list"],
                }
        except Exception as e:
            log_warning(f"Failed to load map '{tier_id}' from Supabase: {e}. Falling back to disk.")
        return None

    def list_available_tiers(self) -> List[MapTierSummary]:
        """Query and return all available road network tiers from Supabase or built-in registry."""
        url = self._settings.SUPABASE_URL
        key = self._settings.SUPABASE_KEY

        if url and key:
            try:
                from app.utils.supabase_map_seeder import get_supabase_client, resolve_table_name
                client = get_supabase_client(url, key)
                target_table = resolve_table_name(client, "task5_city_maps")
                res = client.table(target_table).select(
                    "tier_id, tier_level, display_name, description, node_count, bin_count, intersection_count, edge_count, total_waste_kg"
                ).order("tier_level").execute()
                if res.data:
                    return [
                        MapTierSummary(
                            tier_id=row["tier_id"],
                            tier_level=row.get("tier_level", 1),
                            display_name=row.get("display_name", row["tier_id"]),
                            description=row.get("description"),
                            node_count=row.get("node_count", 0),
                            bin_count=row.get("bin_count", 0),
                            intersection_count=row.get("intersection_count", 0),
                            edge_count=row.get("edge_count", 0),
                            total_waste_kg=float(row.get("total_waste_kg", 0)),
                            is_active=(row["tier_id"] == self._current_tier_id),
                        )
                        for row in res.data
                    ]
            except Exception as e:
                log_warning(f"Could not fetch tier list from Supabase: {e}. Returning built-in tier summaries.")

        # Fallback tier summaries if Supabase query fails
        from app.utils.supabase_map_seeder import MAP_TIER_CONFIGS
        tier_counts = {
            "tier1_sparse": {"nodes": 37, "bins": 15, "intersections": 20, "edges": 42, "waste": 6000.0},
            "tier2_medium": {"nodes": 87, "bins": 45, "intersections": 40, "edges": 141, "waste": 18000.0},
            "tier3_dense": {"nodes": 182, "bins": 120, "intersections": 60, "edges": 423, "waste": 48000.0},
        }
        return [
            MapTierSummary(
                tier_id=cfg["tier_id"],
                tier_level=cfg["tier_level"],
                display_name=cfg["display_name"],
                description=cfg["description"],
                node_count=tier_counts.get(cfg["tier_id"], {}).get("nodes", 0),
                bin_count=tier_counts.get(cfg["tier_id"], {}).get("bins", 0),
                intersection_count=tier_counts.get(cfg["tier_id"], {}).get("intersections", 0),
                edge_count=tier_counts.get(cfg["tier_id"], {}).get("edges", 0),
                total_waste_kg=tier_counts.get(cfg["tier_id"], {}).get("waste", 0.0),
                is_active=(cfg["tier_id"] == self._current_tier_id),
            )
            for cfg in MAP_TIER_CONFIGS
        ]

    def _resolve_file_path(self, tier_id: str) -> Path:
        """Resolve map file path with automated discovery if configured path is missing."""
        if self._custom_map_path:
            p = Path(self._custom_map_path)
            if not p.is_absolute():
                p = (self._settings.BASE_DIR / p).resolve()
            if p.exists():
                return p

        # Map tier_id to filename candidate
        tier_filename = f"city_map_{tier_id}.json"
        candidates = [
            self._settings.BASE_DIR / "data" / tier_filename,
            Path(f"data/{tier_filename}").resolve(),
            self._settings.resolved_map_data_path,
            self._settings.BASE_DIR / "data" / "city_map_tier3_dense.json",
            self._settings.BASE_DIR / "data" / "city_map_tier2_medium.json",
            self._settings.BASE_DIR / "data" / "city_map_tier1_sparse.json",
        ]

        for cand in candidates:
            if cand.exists():
                return cand.resolve()

        return self._settings.resolved_map_data_path

    def _generate_synthetic_fallback_map(self) -> dict:
        """Generate a minimal connected default map topology when no map sources are available."""
        log_warning("No map data available from Supabase or disk. Initializing emergency synthetic default map.")
        return {
            "nodes": [
                {"id": "D0", "type": "start", "lat": 40.7580, "lon": -73.9995, "weight_kg": 0},
                {"id": "T1", "type": "destination", "lat": 40.7180, "lon": -73.9750, "weight_kg": 0},
                {"id": "I1", "type": "intersection", "lat": 40.7500, "lon": -73.9850, "weight_kg": 0},
                {"id": "B1", "type": "bin", "lat": 40.7400, "lon": -73.9800, "weight_kg": 400},
                {"id": "B2", "type": "bin", "lat": 40.7300, "lon": -73.9900, "weight_kg": 400},
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
        """Load map data from Supabase (or fallback to local disk) and build NetworkX graph."""
        data: Optional[dict] = None
        target_tier = self._resolve_target_tier()
        self._current_tier_id = target_tier

        # 1. Primary Strategy: Load directly from Supabase database
        if self._settings.USE_SUPABASE_MAP:
            data = self._load_from_supabase(target_tier)
            if data:
                self._loaded_source = f"supabase:{target_tier}"
                self._loaded_path = Path(f"supabase/{target_tier}")

        # 2. Secondary Strategy: Fall back to local disk JSON if Supabase is disabled or unreachable
        if data is None:
            file_path = self._resolve_file_path(target_tier)
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._loaded_source = str(file_path)
                    self._loaded_path = file_path
                except Exception as e:
                    log_error("Map Parsing Error", f"Failed to parse JSON map file at '{file_path}': {e}")
                    data = self._generate_synthetic_fallback_map()
                    self._loaded_source = "synthetic_fallback"
                    self._loaded_path = file_path
            else:
                data = self._generate_synthetic_fallback_map()
                self._loaded_source = "synthetic_fallback"
                self._loaded_path = file_path

        if not isinstance(data, dict):
            data = self._generate_synthetic_fallback_map()

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
                    lat=0.0,
                    lon=0.0,
                    weight_kg=0,
                )
                nodes_dict[source_id] = synthetic_src
                nodes_list.append(synthetic_src)
                graph.add_node(source_id, type="intersection", lat=0.0, lon=0.0, weight_kg=0)

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
                        lat=0.0,
                        lon=0.0,
                        weight_kg=0,
                    )
                    nodes_dict[target_id] = synthetic_tgt
                    nodes_list.append(synthetic_tgt)
                    graph.add_node(target_id, type="intersection", lat=0.0, lon=0.0, weight_kg=0)

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
            f"{len(edges_list)} edges from '{self.loaded_source}'"
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

    def reload(self, custom_path: Optional[str] = None, tier_id: Optional[str] = None) -> None:
        """Force reloads map data from Supabase tier or custom dataset."""
        if tier_id is not None:
            self._custom_tier_id = Settings.resolve_tier_id_from_path(tier_id)
            self._custom_map_path = None
        elif custom_path is not None:
            self._custom_tier_id = Settings.resolve_tier_id_from_path(custom_path)
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
            map_source=self.loaded_source,
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

