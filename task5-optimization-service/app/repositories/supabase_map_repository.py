"""Read the frontend-ready Task 5 city map payload from Supabase."""

from typing import Any, Dict, Optional

import httpx

from app.config.settings import Settings, get_settings


class SupabaseMapRepository:
    """Repository for the ``enlarged_city_map_payload`` Supabase view."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def get_enlarged_city_map(self) -> Dict[str, Any]:
        """Fetch and return the single enlarged city map payload row."""
        url = (
            f"{self._settings.SUPABASE_URL.rstrip('/')}/rest/v1/"
            f"{self._settings.SUPABASE_MAP_VIEW}"
        )
        headers = {
            "apikey": self._settings.SUPABASE_KEY,
            "Authorization": f"Bearer {self._settings.SUPABASE_KEY}",
            "Accept": "application/json",
        }
        params = {"select": "*", "limit": "1"}

        if self._client is not None:
            response = self._client.get(url, headers=headers, params=params)
        else:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, headers=headers, params=params)

        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise LookupError(
                f"Supabase view '{self._settings.SUPABASE_MAP_VIEW}' returned no map payload."
            )

        payload = rows[0]
        if not isinstance(payload, dict):
            raise ValueError("Supabase returned an invalid city map payload.")
        return payload
