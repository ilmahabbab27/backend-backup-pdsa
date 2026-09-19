from copy import deepcopy

from fastapi.testclient import TestClient

from app import main
from app.allocation import Requirement


class FakeDatabase:
    def __init__(self):
        self.rows = {
            "resource_requests": [
                {"request_code": "E1", "priority": "Critical", "incident_location_key": "city-hall", "status": "open",
                 "metadata": {"required_vehicle_type": "Ambulance", "deadline_minutes": 20, "custom_note": "keep me"}},
                {"request_code": "E2", "priority": "Low", "incident_location_key": "city-hall", "status": "resolved", "metadata": {}},
            ],
            "emergency_vehicles": [
                {"vehicle_code": "A1", "vehicle_type": "Ambulance", "status": "available", "current_location_key": "hospital",
                 "metadata": {"response_minutes": 5, "capabilities": ["oxygen"]}},
                {"vehicle_code": "A2", "vehicle_type": "Ambulance", "status": "busy", "current_location_key": "hospital",
                 "metadata": {"response_minutes": 5, "available_in_minutes": 12}},
            ],
            "resource_allocation_runs": [],
        }

    def table(self, table):
        database = self
        class Query:
            def __init__(self):
                self.filters = []
                self.operation = "select"
                self.payload = None
            def select(self, *args): return self
            def order(self, *args, **kwargs): return self
            def limit(self, *args): return self
            def eq(self, key, value):
                self.filters.append((key, value))
                return self
            def insert(self, body):
                self.operation, self.payload = "insert", body
                return self
            def update(self, body):
                self.operation, self.payload = "update", body
                return self
            def execute(self):
                rows = database.rows[table]
                selected = [row for row in rows if all(row.get(k) == v for k, v in self.filters)]
                if self.operation == "insert":
                    rows.append(deepcopy(self.payload))
                    selected = [self.payload]
                elif self.operation == "update":
                    for row in selected:
                        row.update(deepcopy(self.payload))
                self.data = deepcopy(selected)
                return self
        return Query()


def setup(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(main, "get_database", lambda: database)
    return database, TestClient(main.app)


def test_api_filters_inactive_and_busy_and_previews_do_not_mutate(monkeypatch):
    database, client = setup(monkeypatch)
    original = deepcopy(database.rows)
    for strategy in ("greedy", "min_cost_flow", "genetic"):
        response = client.post("/api/resource/optimize", json={"strategy": strategy})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["total_requests"] == 1
        assert result["assignments"][0]["vehicle"] == "A1"
        assert result["availability_schedule"][-1] == {"vehicle": "A2", "available_in_minutes": 12}
    assert database.rows == original


def test_api_explicit_empty_selections_and_invalid_inputs(monkeypatch):
    _, client = setup(monkeypatch)
    empty = client.post("/api/resource/optimize", json={"strategy": "greedy", "selected_requests": []})
    assert empty.json()["total_requests"] == 0
    no_vehicles = client.post("/api/resource/optimize", json={"strategy": "greedy", "selected_vehicles": []})
    assert no_vehicles.json()["served"] == 0
    for payload in [{"strategy": "backtracking"}, {"strategy": "genetic", "population_size": 1},
                    {"strategy": "greedy", "station_reserves": {"S1": -1}},
                    {"strategy": "greedy", "request_count": 201}]:
        assert client.post("/api/resource/optimize", json=payload).status_code == 422


def test_multi_resource_metadata_round_trip_and_legacy_edit_preservation(monkeypatch):
    database, client = setup(monkeypatch)
    database.rows["resource_requests"][0]["metadata"]["requirements"] = [
        {"vehicle_type": "Ambulance", "quantity": 2, "capabilities": ["oxygen"]}]
    payload = {"request_code": "E1", "requester_name": "Incident", "priority": "High",
               "incident_location_key": "city-hall", "deadline_minutes": 15,
               "required_vehicle_type": "Ambulance", "status": "open"}
    response = client.patch("/api/resource/requests/E1", json=payload)
    assert response.status_code == 200, response.text
    metadata = response.json()["metadata"]
    assert metadata["custom_note"] == "keep me"
    assert metadata["requirements"][0]["quantity"] == 2
    result = client.post("/api/resource/optimize", json={"strategy": "min_cost_flow"}).json()
    assert result["required_units"] == 2
    assert result["partial"] == 1
    assert result["coverage"] == 0


def test_new_request_with_multiple_types_and_low_priority(monkeypatch):
    _, client = setup(monkeypatch)
    response = client.post("/api/resource/requests", json={"request_code": "E3", "requester_name": "Test",
        "priority": "Low", "incident_location_key": "city-hall", "deadline_minutes": 30,
        "requirements": [{"vehicle_type": "Ambulance", "quantity": 2}, {"vehicle_type": "Fire Engine", "quantity": 1}]})
    assert response.status_code == 201, response.text
    assert len(response.json()["metadata"]["requirements"]) == 2


def test_history_uses_real_strategy_and_failure_is_visible(monkeypatch):
    database, client = setup(monkeypatch)
    result = client.post("/api/resource/optimize", json={"strategy": "min_cost_flow", "persist_history": True})
    assert result.status_code == 200
    assert database.rows["resource_allocation_runs"][0]["strategy"] == "min_cost_flow"
    original_table = database.table
    def fail_history(name):
        if name == "resource_allocation_runs":
            raise RuntimeError("history unavailable")
        return original_table(name)
    database.table = fail_history
    response = client.post("/api/resource/optimize", json={"strategy": "greedy", "persist_history": True})
    assert response.status_code == 200
    assert response.json()["warnings"]


def test_stored_profile_drives_assignment_not_incident_index(monkeypatch):
    database, client = setup(monkeypatch)
    database.rows["emergency_vehicles"][0]["metadata"]["response_times"] = {"city-hall": 17}
    result = client.post("/api/resource/optimize", json={"strategy": "greedy"}).json()
    assert result["assignments"][0]["response_minutes"] == 17


def test_real_benchmark_calls_each_strategy_and_measures_memory(monkeypatch):
    _, client = setup(monkeypatch)
    original = main.benchmark_dataset
    monkeypatch.setattr(main, "benchmark_dataset", lambda count: original(4))
    response = client.post("/api/resource/benchmark")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 12
    assert {row["strategy"] for row in rows} == {"greedy", "min_cost_flow", "genetic"}
    assert all(row["runtime_ms"] > 0 and row["peak_memory_kb"] > 0 and row["repetitions"] == 3 for row in rows)
