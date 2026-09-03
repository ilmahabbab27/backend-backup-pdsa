from uuid import UUID

from fastapi.testclient import TestClient

from app.api.network import get_network_repository
from app.main import app
from app.models.network_models import Location, Road
from app.repositories.network_repository import NetworkRepositoryError


class FakeRepository:
    def get_locations(self) -> list[Location]:
        return [
            Location(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                location_key="A",
                name="Alpha",
                type="intersection",
            ),
            Location(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                location_key="B",
                name="Beta",
                type="intersection",
            ),
        ]

    def get_roads(self) -> list[Road]:
        return [
            Road(
                id=UUID("00000000-0000-0000-0000-000000000003"),
                from_location_key="A",
                to_location_key="B",
                distance_km=1.5,
                is_bidirectional=True,
            )
        ]


class FailingRepository:
    def get_locations(self) -> list[Location]:
        raise NetworkRepositoryError("secret connection details")

    def get_roads(self) -> list[Road]:
        raise NetworkRepositoryError("secret connection details")


def client_with(repository: object) -> TestClient:
    app.dependency_overrides[get_network_repository] = lambda: repository
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_health_still_works() -> None:
    response = client_with(FakeRepository()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "task3-network-service"}


def test_nodes_endpoint_returns_selectable_locations() -> None:
    response = client_with(FakeRepository()).get("/api/network/nodes")

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [
            {"location_key": "A", "name": "Alpha", "type": "intersection"},
            {"location_key": "B", "name": "Beta", "type": "intersection"},
        ]
    }


def test_analysis_endpoint_returns_complete_schema() -> None:
    response = client_with(FakeRepository()).get("/api/network/analysis/A")

    assert response.status_code == 200
    body = response.json()
    assert body["start_node"] == "A"
    assert body["start_location_name"] == "Alpha"
    assert body["total_nodes"] == 2
    assert body["total_edges"] == 1
    assert body["network_density"] == 1.0
    assert body["bfs"]["traversal_order"] == ["A", "B"]
    assert body["dfs"]["visited_count"] == 2
    assert body["most_connected_location"]["location_key"] == "A"
    assert len(body["centrality"]) == 2
    assert body["metrics_execution_time_ms"] >= 0
    assert body["total_execution_time_ms"] >= 0


def test_invalid_node_returns_404_with_useful_message() -> None:
    response = client_with(FakeRepository()).get("/api/network/analysis/MISSING")

    assert response.status_code == 404
    assert "MISSING" in response.json()["detail"]


def test_nodes_repository_failure_returns_sanitized_503() -> None:
    response = client_with(FailingRepository()).get("/api/network/nodes")

    assert response.status_code == 503
    assert response.json() == {"detail": "Network data is temporarily unavailable"}
    assert "secret" not in response.text


def test_analysis_repository_failure_returns_sanitized_503() -> None:
    response = client_with(FailingRepository()).get("/api/network/analysis/A")

    assert response.status_code == 503
    assert response.json() == {"detail": "Network data is temporarily unavailable"}
    assert "secret" not in response.text


def test_configured_cors_origin_is_allowed() -> None:
    response = client_with(FakeRepository()).options(
        "/api/network/nodes",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unconfigured_cors_origin_is_not_allowed() -> None:
    response = client_with(FakeRepository()).options(
        "/api/network/nodes",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
