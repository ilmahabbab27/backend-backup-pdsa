"""Read the frontend-ready Task 5 city map payload from Supabase."""

from typing import Any, Dict, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.repositories.map_repository import MapRepository


class SupabaseMapRepository:
    """Repository for the ``enlarged_city_map_payload`` Supabase view or map tables."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        map_repo: Optional[MapRepository] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._map_repo = map_repo
        self._client = client

    def _ensure_edges_in_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure the payload contains a valid 'edges' list expected by the frontend UI."""
        if isinstance(payload.get("edges"), list) and len(payload["edges"]) > 0:
            return payload

        # Build edges list from adjacency_list if missing or empty
        adj = payload.get("adjacency_list", {})
        edges_list = []
        seen_edges = set()

        if isinstance(adj, dict):
            for u, neighbors in adj.items():
                if not isinstance(neighbors, list):
                    continue
                for nbr in neighbors:
                    if not isinstance(nbr, dict):
                        continue
                    v = str(nbr.get("target", "")).strip()
                    if not v:
                        continue
                    try:
                        dist = float(nbr.get("distance_km", 1.0))
                    except (ValueError, TypeError):
                        dist = 1.0

                    edge_key = tuple(sorted([str(u), v]))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges_list.append({
                            "source": edge_key[0],
                            "target": edge_key[1],
                            "distance_km": dist,
                        })

        payload["edges"] = edges_list
        return payload

    def get_enlarged_city_map(self) -> Dict[str, Any]:
        """Fetch and return the single enlarged city map payload row from Supabase or local map repository."""
        headers = {
            "apikey": self._settings.SUPABASE_KEY or "",
            "Authorization": f"Bearer {self._settings.SUPABASE_KEY or ''}",
            "Accept": "application/json",
        }

        tier_id = (
            self._map_repo.current_tier_id
            if self._map_repo
            else (self._settings.SUPABASE_MAP_TIER or "tier3_dense")
        )

        # Try fetching from Supabase table or view endpoints
        if self._settings.SUPABASE_URL and self._settings.SUPABASE_KEY:
            base_url = self._settings.SUPABASE_URL.rstrip("/")

            candidates = [
                (f"{base_url}/rest/v1/task5_city_maps", {"tier_id": f"eq.{tier_id}", "select": "*", "limit": "1"}),
                (f"{base_url}/rest/v1/city_maps", {"tier_id": f"eq.{tier_id}", "select": "*", "limit": "1"}),
                (f"{base_url}/rest/v1/enlarged_city_map_payload", {"select": "*", "limit": "1"}),
            ]

            for url, params in candidates:
                try:
                    if self._client is not None:
                        response = self._client.get(url, headers=headers, params=params)
                    else:
                        with httpx.Client(timeout=10.0) as client:
                            response = client.get(url, headers=headers, params=params)

                    if response.status_code == 200:
                        rows = response.json()
                        if isinstance(rows, list) and len(rows) > 0 and isinstance(rows[0], dict):
                            payload = rows[0]
                            if "tier_id" not in payload or payload.get("tier_id") == tier_id:
                                return self._ensure_edges_in_payload(payload)
                except Exception:
                    continue

        # Fallback strategy: Load map from MapRepository (disk JSON or fallback topology)
        map_repo = self._map_repo or MapRepository(settings=self._settings, tier_id=tier_id)
        return self._ensure_edges_in_payload(map_repo.get_full_map().model_dump())
