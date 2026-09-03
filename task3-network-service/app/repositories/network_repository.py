"""Supabase access for city locations and roads."""

from supabase import Client, create_client

from app.config.settings import Settings, get_settings
from app.models.network_models import Location, Road


class NetworkRepositoryError(RuntimeError):
    """Raised when network data cannot be obtained from Supabase."""


class NetworkRepository:
    """Read location and road records from Supabase."""

    def __init__(
        self,
        client: Client | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client or self._create_client(settings or get_settings())

    @staticmethod
    def _create_client(settings: Settings) -> Client:
        if not settings.supabase_url or not settings.supabase_key:
            raise NetworkRepositoryError(
                "SUPABASE_URL and SUPABASE_KEY must be set to access network data"
            )

        try:
            return create_client(settings.supabase_url, settings.supabase_key)
        except Exception as exc:
            raise NetworkRepositoryError("Failed to create the Supabase client") from exc

    def get_locations(self) -> list[Location]:
        """Fetch and validate every location record."""
        try:
            response = self._client.table("locations").select("*").execute()
            return [Location.model_validate(row) for row in response.data]
        except Exception as exc:
            raise NetworkRepositoryError("Failed to fetch locations from Supabase") from exc

    def get_roads(self) -> list[Road]:
        """Fetch and validate every road record."""
        try:
            response = self._client.table("roads").select("*").execute()
            return [Road.model_validate(row) for row in response.data]
        except Exception as exc:
            raise NetworkRepositoryError("Failed to fetch roads from Supabase") from exc
