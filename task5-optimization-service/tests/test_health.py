"""Health check tests."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    """Test the root /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "task5-optimization-service"
    assert "timestamp" in data


def test_v1_health_check() -> None:
    """Test the /api/v1/health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "task5-optimization-service"
    assert "timestamp" in data
