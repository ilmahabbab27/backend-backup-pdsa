"""Integration tests for FastAPI Route Service endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health():
    """Verify health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "task1-route-service"}


def test_api_get_cities():
    """Verify retrieving city list."""
    response = client.get("/api/route/cities")
    assert response.status_code == 200
    cities = response.json()
    assert isinstance(cities, list)
    assert len(cities) >= 10
    assert any(c["id"] == "city-hall" for c in cities)


def test_api_get_network():
    """Verify network topology endpoint."""
    response = client.get("/api/route/network")
    assert response.status_code == 200
    data = response.json()
    assert "cities" in data
    assert "roads" in data
    assert data["total_cities"] >= 10
    assert data["total_roads"] >= 15


def test_api_plan_route_astar():
    """Verify route planning with A*."""
    payload = {
        "start": "city-hall",
        "destination": "central-hospital",
        "algorithm": "astar",
    }
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "A*"
    assert data["start"] == "city-hall"
    assert data["destination"] == "central-hospital"
    assert data["route"] == ["city-hall", "bus-station", "central-hospital"]
    assert data["distance"] == 4.0
    assert data["nodes_explored"] >= 2
    assert data["execution_time_ms"] >= 0.0


def test_api_plan_route_bfs():
    """Verify route planning with BFS (finds 1-hop path)."""
    payload = {
        "start": "city-hall",
        "destination": "central-hospital",
        "algorithm": "bfs",
    }
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "BFS"
    assert data["hops"] == 1
    assert data["distance"] == 8.0


def test_api_compare():
    """Verify route comparison endpoint."""
    payload = {
        "start": "city-hall",
        "destination": "central-hospital",
    }
    response = client.post("/api/route/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["start"] == "city-hall"
    assert data["destination"] == "central-hospital"
    assert len(data["results"]) == 3
    assert "analysis" in data


def test_api_error_invalid_city():
    """Verify 404 for non-existent city."""
    payload = {
        "start": "non-existent-1",
        "destination": "city-hall",
        "algorithm": "dijkstra",
    }
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_api_error_disconnected_destination():
    """Verify 404 for unreachable node."""
    payload = {
        "start": "city-hall",
        "destination": "isolated-outpost",
        "algorithm": "dijkstra",
    }
    response = client.post("/api/route/plan", json=payload)
    assert response.status_code == 404
    assert "No route found" in response.json()["detail"]


def test_api_benchmark():
    """Verify benchmark execution."""
    response = client.post("/api/route/benchmark?iterations=5")
    assert response.status_code == 200
    data = response.json()
    assert data["runs_averaged"] == 5
    assert len(data["tiers"]) == 3
    for tier in data["tiers"]:
        assert tier["node_count"] > 0
        assert tier["bfs_time_ms"] >= 0.0
        assert tier["dijkstra_time_ms"] >= 0.0
        assert tier["astar_time_ms"] >= 0.0
