"""Tests for loading the enlarged city map payload from Supabase."""

import httpx

from app.config.settings import Settings
from app.repositories.supabase_map_repository import SupabaseMapRepository


def test_repository_fetches_single_payload_row() -> None:
    payload = {
        "slug": "enlarged-reference-city-v1",
        "nodes": [],
        "edges": [],
        "areas": [],
        "bins": [],
        "landmarks": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/enlarged_city_map_payload"
        assert request.url.params["select"] == "*"
        assert request.headers["apikey"] == "test-key"
        return httpx.Response(200, json=[payload])

    settings = Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_KEY="test-key",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        repository = SupabaseMapRepository(settings=settings, client=client)
        assert repository.get_enlarged_city_map() == payload
