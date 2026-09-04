"""Repository for loading locations and road networks from Supabase with resilient built-in fallback."""

from typing import Any, Optional
from app.algorithms.graph import Graph
from app.config.supabase_client import get_supabase


# Built-in complete city transportation network matching Smart City seed coordinates and frontend graph
DEFAULT_LOCATIONS: list[dict[str, Any]] = [
    {
        "id": "city-hall",
        "name": "City Hall",
        "latitude": 6.9271,
        "longitude": 79.8612,
        "x": 440,
        "y": 250,
        "kind": "civic",
    },
    {
        "id": "central-hospital",
        "name": "Central Hospital",
        "latitude": 6.9282,
        "longitude": 79.8631,
        "x": 620,
        "y": 160,
        "kind": "medical",
    },
    {
        "id": "community-hospital",
        "name": "Community Hospital",
        "latitude": 6.9249,
        "longitude": 79.8579,
        "x": 780,
        "y": 250,
        "kind": "medical",
    },
    {
        "id": "police-station",
        "name": "Police Station",
        "latitude": 6.9310,
        "longitude": 79.8645,
        "x": 300,
        "y": 140,
        "kind": "safety",
    },
    {
        "id": "fire-station",
        "name": "Fire Station",
        "latitude": 6.9231,
        "longitude": 79.8604,
        "x": 300,
        "y": 370,
        "kind": "safety",
    },
    {
        "id": "university",
        "name": "University",
        "latitude": 6.9295,
        "longitude": 79.8662,
        "x": 620,
        "y": 380,
        "kind": "education",
    },
    {
        "id": "bus-station",
        "name": "Central Bus Station",
        "latitude": 6.9257,
        "longitude": 79.8626,
        "x": 470,
        "y": 110,
        "kind": "transport",
    },
    {
        "id": "shopping-center",
        "name": "Shopping Center",
        "latitude": 6.9279,
        "longitude": 79.8681,
        "x": 700,
        "y": 470,
        "kind": "commercial",
    },
    {
        "id": "waste-center",
        "name": "Waste Management Center",
        "latitude": 6.9218,
        "longitude": 79.8588,
        "x": 140,
        "y": 250,
        "kind": "utility",
    },
    {
        "id": "residential",
        "name": "Residential District",
        "latitude": 6.9262,
        "longitude": 79.8569,
        "x": 460,
        "y": 490,
        "kind": "residential",
    },
    {
        "id": "public-park",
        "name": "Public Park",
        "latitude": 6.9306,
        "longitude": 79.8599,
        "x": 250,
        "y": 500,
        "kind": "leisure",
    },
    {
        "id": "medical-center",
        "name": "City Medical Center",
        "latitude": 6.9235,
        "longitude": 79.8710,
        "x": 830,
        "y": 380,
        "kind": "medical",
    },
    {
        "id": "service-center",
        "name": "Public Service Center",
        "latitude": 6.9335,
        "longitude": 79.8580,
        "x": 190,
        "y": 60,
        "kind": "civic",
    },
    {
        "id": "industrial-zone",
        "name": "Industrial Zone",
        "latitude": 6.9180,
        "longitude": 79.8550,
        "x": 100,
        "y": 420,
        "kind": "utility",
    },
    {
        "id": "riverside",
        "name": "Riverside Suburb",
        "latitude": 6.9350,
        "longitude": 79.8730,
        "x": 860,
        "y": 90,
        "kind": "residential",
    },
    # Disconnected island / outpost for unreachable route tests
    {
        "id": "isolated-outpost",
        "name": "Isolated Outpost",
        "latitude": 6.9950,
        "longitude": 79.9500,
        "x": 920,
        "y": 520,
        "kind": "utility",
    },
]

# Roads configuration.
# Note: direct road from city-hall to central-hospital is 8.0 km (1 hop),
# while city-hall -> bus-station (1.2 km) -> central-hospital (2.8 km) = 4.0 km (2 hops).
# This provides a realistic demonstration where BFS chooses the 1-hop path (8.0 km),
# while Dijkstra & A* choose the 2-hop optimal path (4.0 km).
DEFAULT_ROADS: list[dict[str, Any]] = [
    {"source": "city-hall", "destination": "bus-station", "distance_km": 1.2, "travel_time_min": 3.0},
    {"source": "bus-station", "destination": "central-hospital", "distance_km": 2.8, "travel_time_min": 6.0},
    {"source": "city-hall", "destination": "central-hospital", "distance_km": 8.0, "travel_time_min": 15.0},
    {"source": "city-hall", "destination": "police-station", "distance_km": 1.0, "travel_time_min": 2.5},
    {"source": "city-hall", "destination": "fire-station", "distance_km": 2.2, "travel_time_min": 5.0},
    {"source": "city-hall", "destination": "university", "distance_km": 3.4, "travel_time_min": 7.0},
    {"source": "city-hall", "destination": "residential", "distance_km": 3.0, "travel_time_min": 6.0},
    {"source": "city-hall", "destination": "shopping-center", "distance_km": 4.6, "travel_time_min": 10.0},
    {"source": "city-hall", "destination": "service-center", "distance_km": 4.1, "travel_time_min": 9.0},
    {"source": "bus-station", "destination": "police-station", "distance_km": 2.0, "travel_time_min": 4.0},
    {"source": "bus-station", "destination": "riverside", "distance_km": 6.2, "travel_time_min": 14.0},
    {"source": "bus-station", "destination": "service-center", "distance_km": 3.6, "travel_time_min": 8.0},
    {"source": "bus-station", "destination": "university", "distance_km": 5.1, "travel_time_min": 11.0},
    {"source": "central-hospital", "destination": "community-hospital", "distance_km": 2.7, "travel_time_min": 6.0},
    {"source": "central-hospital", "destination": "riverside", "distance_km": 3.4, "travel_time_min": 8.0},
    {"source": "central-hospital", "destination": "university", "distance_km": 2.9, "travel_time_min": 7.0},
    {"source": "community-hospital", "destination": "medical-center", "distance_km": 2.3, "travel_time_min": 5.0},
    {"source": "community-hospital", "destination": "residential", "distance_km": 1.4, "travel_time_min": 3.5},
    {"source": "police-station", "destination": "fire-station", "distance_km": 1.5, "travel_time_min": 4.0},
    {"source": "fire-station", "destination": "community-hospital", "distance_km": 2.2, "travel_time_min": 5.0},
    {"source": "fire-station", "destination": "waste-center", "distance_km": 2.0, "travel_time_min": 4.5},
    {"source": "university", "destination": "shopping-center", "distance_km": 1.9, "travel_time_min": 4.0},
    {"source": "university", "destination": "medical-center", "distance_km": 3.2, "travel_time_min": 7.0},
    {"source": "shopping-center", "destination": "residential", "distance_km": 2.6, "travel_time_min": 5.5},
    {"source": "shopping-center", "destination": "public-park", "distance_km": 1.7, "travel_time_min": 4.0},
    {"source": "residential", "destination": "waste-center", "distance_km": 3.3, "travel_time_min": 7.0},
    {"source": "residential", "destination": "public-park", "distance_km": 2.1, "travel_time_min": 4.5},
    {"source": "public-park", "destination": "fire-station", "distance_km": 1.8, "travel_time_min": 4.0},
    {"source": "waste-center", "destination": "industrial-zone", "distance_km": 1.9, "travel_time_min": 4.0},
    {"source": "industrial-zone", "destination": "public-park", "distance_km": 2.4, "travel_time_min": 5.0},
]


class NetworkRepository:
    """Repository handling city locations and road network topology."""

    def __init__(self) -> None:
        self._supabase = get_supabase()

    def get_locations(self) -> list[dict[str, Any]]:
        """Retrieve all city locations from Supabase or fallback data."""
        if self._supabase:
            try:
                resp = (
                    self._supabase.table("locations")
                    .select("location_key, name, type, latitude, longitude, metadata")
                    .execute()
                )
                if resp.data and len(resp.data) > 0:
                    locations = []
                    for row in resp.data:
                        loc_key = row.get("location_key")
                        meta = row.get("metadata") or {}
                        # Merge with x/y if present in default list
                        default_match = next(
                            (l for l in DEFAULT_LOCATIONS if l["id"] == loc_key),
                            None,
                        )
                        locations.append(
                            {
                                "id": loc_key,
                                "name": row.get("name", loc_key),
                                "latitude": float(row.get("latitude") or 0.0),
                                "longitude": float(row.get("longitude") or 0.0),
                                "x": default_match["x"] if default_match else meta.get("x", 400),
                                "y": default_match["y"] if default_match else meta.get("y", 300),
                                "kind": row.get("type", "city"),
                                "metadata": meta,
                            }
                        )
                    return locations
            except Exception as exc:
                print(f"[REPO WARNING] Supabase query failed, using built-in locations: {exc}")

        return [dict(loc) for loc in DEFAULT_LOCATIONS]

    def get_roads(self) -> list[dict[str, Any]]:
        """Retrieve all roads from Supabase or fallback data."""
        if self._supabase:
            try:
                resp = (
                    self._supabase.table("roads")
                    .select(
                        "from_location_key, to_location_key, distance_km, travel_time_min, is_bidirectional, metadata"
                    )
                    .execute()
                )
                if resp.data and len(resp.data) > 0:
                    roads = []
                    for row in resp.data:
                        roads.append(
                            {
                                "source": row.get("from_location_key"),
                                "destination": row.get("to_location_key"),
                                "distance_km": float(row.get("distance_km") or 1.0),
                                "travel_time_min": float(row.get("travel_time_min") or 0.0),
                                "is_bidirectional": bool(row.get("is_bidirectional", True)),
                                "metadata": row.get("metadata") or {},
                            }
                        )
                    return roads
            except Exception as exc:
                print(f"[REPO WARNING] Supabase query failed, using built-in roads: {exc}")

        return [dict(road) for road in DEFAULT_ROADS]

    def build_graph(self) -> Graph:
        """Construct an in-memory Graph instance using adjacency list."""
        locations = self.get_locations()
        roads = self.get_roads()

        graph = Graph(is_directed=False)

        for loc in locations:
            graph.add_node(
                node_id=loc["id"],
                name=loc["name"],
                latitude=loc["latitude"],
                longitude=loc["longitude"],
                x=loc.get("x"),
                y=loc.get("y"),
                kind=loc.get("kind", "city"),
                metadata=loc.get("metadata", {}),
            )

        for road in roads:
            graph.add_edge(
                source=road["source"],
                destination=road["destination"],
                distance_km=road["distance_km"],
                travel_time_min=road.get("travel_time_min"),
                is_bidirectional=road.get("is_bidirectional", True),
                metadata=road.get("metadata", {}),
            )

        return graph
