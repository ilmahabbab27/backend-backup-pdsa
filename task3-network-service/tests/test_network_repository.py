from types import SimpleNamespace
from uuid import UUID

import pytest

from app.repositories.network_repository import NetworkRepository, NetworkRepositoryError


LOCATION_ID = UUID("00000000-0000-0000-0000-000000000001")
ROAD_ID = UUID("00000000-0000-0000-0000-000000000002")


class FakeQuery:
    def __init__(self, data: list[dict] | None = None, error: Exception | None = None) -> None:
        self.data = data or []
        self.error = error
        self.selected = ""

    def select(self, columns: str) -> "FakeQuery":
        self.selected = columns
        return self

    def execute(self) -> SimpleNamespace:
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.data)


class FakeSupabase:
    def __init__(self, tables: dict[str, FakeQuery]) -> None:
        self.tables = tables
        self.requested_tables: list[str] = []

    def table(self, name: str) -> FakeQuery:
        self.requested_tables.append(name)
        return self.tables[name]


def test_get_locations_uses_mock_supabase() -> None:
    query = FakeQuery(
        [{
            "id": str(LOCATION_ID),
            "location_key": "CITY_HALL",
            "name": "City Hall",
            "type": "administrative",
            "latitude": 6.9271,
            "longitude": 79.8612,
            "metadata": {"zone": "central"},
        }]
    )
    client = FakeSupabase({"locations": query})

    locations = NetworkRepository(client=client).get_locations()

    assert client.requested_tables == ["locations"]
    assert query.selected == "*"
    assert locations[0].id == LOCATION_ID
    assert locations[0].location_key == "CITY_HALL"


def test_get_roads_uses_mock_supabase() -> None:
    query = FakeQuery(
        [{
            "id": str(ROAD_ID),
            "from_location_key": "CITY_HALL",
            "to_location_key": "HOSPITAL",
            "distance_km": "2.50",
            "travel_time_min": None,
            "is_bidirectional": True,
            "metadata": {},
        }]
    )
    client = FakeSupabase({"roads": query})

    roads = NetworkRepository(client=client).get_roads()

    assert client.requested_tables == ["roads"]
    assert query.selected == "*"
    assert roads[0].id == ROAD_ID
    assert roads[0].distance_km == 2.5
    assert roads[0].travel_time_min is None


@pytest.mark.parametrize(
    ("method_name", "table_name", "message"),
    [
        ("get_locations", "locations", "Failed to fetch locations from Supabase"),
        ("get_roads", "roads", "Failed to fetch roads from Supabase"),
    ],
)
def test_repository_wraps_supabase_failures(
    method_name: str,
    table_name: str,
    message: str,
) -> None:
    client = FakeSupabase({table_name: FakeQuery(error=RuntimeError("database unavailable"))})
    repository = NetworkRepository(client=client)

    with pytest.raises(NetworkRepositoryError, match=message) as exc_info:
        getattr(repository, method_name)()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
