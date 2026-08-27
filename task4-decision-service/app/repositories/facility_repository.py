"""Database access for the Public Facility Recommender.

All Supabase reads live here, per the project rule that database operations
belong in repositories/. The service layer never talks to Supabase directly.
"""
from typing import Any, Optional

from app.config.supabase_client import get_supabase


class FacilityRepository:
    """Reads facilities and locations from Supabase."""

    def get_location(self, location_key: str) -> Optional[dict[str, Any]]:
        """Return a single location row by its key, or None if not found."""
        resp = (
            get_supabase()
            .table("locations")
            .select("location_key, name, latitude, longitude")
            .eq("location_key", location_key)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def get_facilities_by_type(
        self, facility_type: str
    ) -> list[dict[str, Any]]:
        """Return all facilities of a given type, joined with their location.

        We fetch the facility rows, then the matching location rows, and merge
        them in Python. (Two simple queries keep this readable and avoid
        relying on a specific PostgREST embed configuration.)
        """
        facilities_resp = (
            get_supabase()
            .table("facilities")
            .select(
                "location_key, facility_type, capacity, current_load, "
                "priority_score"
            )
            .eq("facility_type", facility_type)
            .execute()
        )
        facilities = facilities_resp.data or []
        if not facilities:
            return []

        keys = [f["location_key"] for f in facilities]
        locations_resp = (
            get_supabase()
            .table("locations")
            .select("location_key, name, latitude, longitude")
            .in_("location_key", keys)
            .execute()
        )
        loc_by_key = {
            loc["location_key"]: loc for loc in (locations_resp.data or [])
        }

        merged: list[dict[str, Any]] = []
        for fac in facilities:
            loc = loc_by_key.get(fac["location_key"], {})
            merged.append(
                {
                    **fac,
                    "name": loc.get("name", fac["location_key"]),
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                }
            )
        return merged
