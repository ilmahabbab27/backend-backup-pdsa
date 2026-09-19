"""FastAPI entry point for the Resource Allocation Service."""

import os
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from statistics import median
from threading import RLock
import tracemalloc
from random import Random
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.allocation import Incident, Vehicle, Requirement, Options, ResponseCache, PRIORITY, STRATEGIES, allocate, canonical
from supabase import Client, create_client

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@lru_cache(maxsize=1)
def get_database() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)

app = FastAPI(title="Resource Allocation Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is available."""
    return {"status": "ok", "service": "task2-resource-service"}


class OptimizationRequest(Options):
    strategy: Literal["greedy", "min_cost_flow", "genetic"]
    request_count: int = Field(default=4, ge=0, le=200)
    vehicle_count: int = Field(default=3, ge=0, le=200)
    selected_vehicles: list[str] | None = Field(default=None, max_length=200)
    selected_requests: list[str] | None = Field(default=None, max_length=200)
    persist_history: bool = False


class RequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    request_code: str = Field(min_length=1, max_length=80)
    requester_name: str = Field(min_length=1, max_length=200)
    priority: Literal["Critical", "High", "Medium", "Low"]
    incident_location_key: str = Field(min_length=1)
    required_vehicle_type: str = Field(default="Ambulance", min_length=1)
    required_quantity: int = Field(default=1, ge=1, le=20)
    required_capabilities: list[str] = Field(default_factory=list, max_length=20)
    requirements: list[Requirement] = Field(default_factory=list, max_length=10)
    deadline_minutes: float = Field(gt=0, le=10080, allow_inf_nan=False)
    status: Literal["open", "assigned", "unassigned", "resolved"] = "open"


class VehicleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    vehicle_code: str = Field(min_length=1, max_length=80)
    vehicle_type: str = Field(min_length=1, max_length=80)
    current_location_key: str = Field(min_length=1)
    response_minutes: float = Field(ge=0, le=10080, allow_inf_nan=False)
    status: Literal["available", "busy", "maintenance", "offline"] = "available"
    station: str | None = None
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    workload: float = Field(default=0, ge=0, le=10000, allow_inf_nan=False)
    available_in_minutes: float = Field(default=0, ge=0, le=10080, allow_inf_nan=False)
    response_times: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_response_times(self):
        from math import isfinite
        if any(not isfinite(v) or v < 0 or v > 10080 for v in self.response_times.values()):
            raise ValueError("Location response times must be finite and between 0 and 10080 minutes.")
        return self


def record_body(payload, table, key=None):
    """Use existing JSON metadata, preserving fields omitted by older clients."""
    request_record = isinstance(payload, RequestCreate)
    columns = ({"request_code", "requester_name", "priority", "incident_location_key", "status"}
               if request_record else {"vehicle_code", "vehicle_type", "current_location_key", "status"})
    values = payload.model_dump(exclude_unset=key is not None)
    metadata = {}
    if key is not None:
        id_column = "request_code" if request_record else "vehicle_code"
        rows = get_database().table(table).select("metadata").eq(id_column, key).execute().data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Record was not found.")
        metadata = dict(rows[0].get("metadata") or {})
    metadata.update({name: value for name, value in values.items() if name not in columns})
    return {**{name: value for name, value in values.items() if name in columns}, "metadata": metadata}


def database_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    message = str(exc)
    if "foreign key" in message.lower() or "location" in message.lower():
        message = "Choose a location that exists in the locations table."
    elif "duplicate" in message.lower() or "unique" in message.lower():
        message = "That code already exists. Use a different code."
    return HTTPException(status_code=400, detail=message)


@app.get("/api/resource/requests", tags=["resource data"])
async def list_requests() -> list[dict]:
    return get_database().table("resource_requests").select("request_code,requester_name,priority,incident_location_key,status,metadata").order("created_at", desc=True).execute().data or []


@app.post("/api/resource/requests", status_code=201, tags=["resource data"])
async def create_request(payload: RequestCreate) -> dict:
    if not payload.request_code.strip() or not payload.requester_name.strip() or not payload.incident_location_key.strip():
        raise HTTPException(status_code=400, detail="Request code, incident name, and location are required.")
    try:
        response = get_database().table("resource_requests").insert(record_body(payload, "resource_requests")).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    return response.data[0]


@app.get("/api/resource/vehicles", tags=["resource data"])
async def list_vehicles() -> list[dict]:
    return get_database().table("emergency_vehicles").select("vehicle_code,vehicle_type,status,current_location_key,metadata").order("vehicle_code").execute().data or []


@app.post("/api/resource/vehicles", status_code=201, tags=["resource data"])
async def create_vehicle(payload: VehicleCreate) -> dict:
    if not payload.vehicle_code.strip() or not payload.vehicle_type.strip() or not payload.current_location_key.strip():
        raise HTTPException(status_code=400, detail="Vehicle code, vehicle type, and location are required.")
    try:
        response = get_database().table("emergency_vehicles").insert(record_body(payload, "emergency_vehicles")).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    return response.data[0]


@app.get("/api/resource/history", tags=["resource history"])
async def list_history() -> list[dict]:
    return get_database().table("resource_allocation_runs").select("id,strategy,served,total_requests,coverage,unassigned,processing_time_ms,created_at").order("created_at", desc=True).limit(50).execute().data or []


@app.patch("/api/resource/requests/{request_code}", tags=["resource data"])
async def update_request(request_code: str, payload: RequestCreate) -> dict:
    try:
        response = get_database().table("resource_requests").update(record_body(payload, "resource_requests", request_code)).eq("request_code", request_code).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    if not response.data:
        raise HTTPException(status_code=404, detail="Request was not found.")
    return response.data[0]


@app.delete("/api/resource/requests/{request_code}", tags=["resource data"])
async def delete_request(request_code: str) -> dict[str, str]:
    try:
        response = get_database().table("resource_requests").delete().eq("request_code", request_code).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    if not response.data:
        raise HTTPException(status_code=404, detail="Request was not found.")
    return {"status": "deleted"}


@app.patch("/api/resource/vehicles/{vehicle_code}", tags=["resource data"])
async def update_vehicle(vehicle_code: str, payload: VehicleCreate) -> dict:
    try:
        response = get_database().table("emergency_vehicles").update(record_body(payload, "emergency_vehicles", vehicle_code)).eq("vehicle_code", vehicle_code).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    if not response.data:
        raise HTTPException(status_code=404, detail="Vehicle was not found.")
    return response.data[0]


@app.delete("/api/resource/vehicles/{vehicle_code}", tags=["resource data"])
async def delete_vehicle(vehicle_code: str) -> dict[str, str]:
    try:
        response = get_database().table("emergency_vehicles").delete().eq("vehicle_code", vehicle_code).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    if not response.data:
        raise HTTPException(status_code=404, detail="Vehicle was not found.")
    return {"status": "deleted"}


PLANNER_LOCK = RLock()


def load_live_data():
    database = get_database()
    request_rows = database.table("resource_requests").select("request_code,priority,incident_location_key,status,metadata").order("created_at").execute().data or []
    vehicle_rows = database.table("emergency_vehicles").select("vehicle_code,vehicle_type,status,current_location_key,metadata").order("vehicle_code").execute().data or []
    incidents = []
    for row in request_rows:
        if row.get("status", "open") not in ("open", "unassigned"):
            continue
        meta = row.get("metadata") or {}
        requirements = meta.get("requirements") or [{
            "vehicle_type": meta.get("required_vehicle_type", "Any suitable vehicle"),
            "quantity": meta.get("required_quantity", 1),
            "capabilities": meta.get("required_capabilities", []),
        }]
        incidents.append(Incident(row["request_code"], row.get("incident_location_key") or "Unknown",
                                  row.get("priority", "Medium").title(), float(meta.get("deadline_minutes", 20)),
                                  tuple(Requirement.model_validate(r) for r in requirements)))
    vehicles = []
    for row in vehicle_rows:
        meta = row.get("metadata") or {}
        vehicles.append(Vehicle(row["vehicle_code"], row["vehicle_type"], row.get("current_location_key") or "Unknown",
                                meta.get("station") or row.get("current_location_key") or "Unspecified",
                                frozenset(canonical(c) for c in meta.get("capabilities", [])),
                                float(meta.get("response_minutes", 10)),
                                {key: float(value) for key, value in (meta.get("response_times") or {}).items()},
                                float(meta.get("workload", 0)), row.get("status", "available"),
                                float(meta.get("available_in_minutes", 0))))
    return incidents, vehicles


@app.post("/api/resource/optimize", tags=["resource allocation"])
def optimize_resources(request: OptimizationRequest):
    try:
        incidents, vehicles = load_live_data()
        selected_requests = set(request.selected_requests) if request.selected_requests is not None else None
        selected_vehicles = set(request.selected_vehicles) if request.selected_vehicles is not None else None
        incidents = sorted((i for i in incidents if selected_requests is None or i.id in selected_requests),
                           key=lambda i: (PRIORITY.get(i.priority, 4), i.deadline, i.id))[:request.request_count]
        # Reserves apply conservatively to the selected available fleet.
        available = [v for v in vehicles if v.status == "available" and
                     (selected_vehicles is None or v.id in selected_vehicles)][:request.vehicle_count]
        upcoming = [v for v in vehicles if v.status == "busy" and v.available_in > 0 and
                    (selected_vehicles is None or v.id in selected_vehicles)]
        with PLANNER_LOCK:
            result = allocate(incidents, available + upcoming, request.strategy, request)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not load or plan Task 2 resources. Check backend data and logs.") from exc
    if request.persist_history:
        try:
            fields = ("strategy", "served", "total_requests", "coverage", "unassigned", "processing_time_ms")
            get_database().table("resource_allocation_runs").insert({key: result[key] for key in fields}).execute()
        except Exception:
            result["warnings"].append("Plan calculated, but history could not be saved. Check the history table and its permissions.")
    return result


def benchmark_dataset(count):
    """Reproducible synthetic inputs; measurements are from the real algorithms."""
    rng = Random(2026 + count)
    kinds = ("Ambulance", "Fire Engine", "Police")
    incidents = [Incident(f"E{i}", f"zone-{i % 8}", list(PRIORITY)[i % 4], 10 + i % 20,
                          (Requirement(vehicle_type=kinds[i % 3]),)) for i in range(count)]
    vehicles = [Vehicle(f"V{i}", kinds[i % 3], f"base-{i % 5}", f"station-{i % 5}", frozenset(),
                        10, {f"zone-{j}": rng.randint(3, 30) for j in range(8)}, workload=i % 4)
                for i in range(max(1, count * 3 // 4))]
    return incidents, vehicles


@app.post("/api/resource/benchmark", tags=["resource allocation"])
def benchmark_resources():
    """Median of three cold-cache runs; separate traced-memory measurement."""
    results = []
    with PLANNER_LOCK:
        for count in (10, 25, 50, 100):
            incidents, vehicles = benchmark_dataset(count)
            for strategy in STRATEGIES:
                runtimes = []
                for seed in (41, 42, 43):
                    options = Options(seed=seed, population_size=16, generations=20, use_cache=False)
                    start = perf_counter()
                    result = allocate(incidents, vehicles, strategy, options, ResponseCache())
                    runtimes.append((perf_counter() - start) * 1000)
                tracemalloc.start()
                try:
                    allocate(incidents, vehicles, strategy, options, ResponseCache())
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                results.append({"incident_count": count, "vehicle_count": len(vehicles), "strategy": strategy,
                                "runtime_ms": round(median(runtimes), 3), "peak_memory_kb": round(peak / 1024, 3),
                                "served": result["served"], "coverage": result["coverage"], "unassigned": result["unassigned"],
                                "total_allocation_cost": result["total_allocation_cost"],
                                "deadline_violations": result["deadline_violations"],
                                "critical_served": result["critical_served"], "repetitions": 3,
                                "dataset": "Seeded synthetic incidents and heterogeneous vehicles",
                                "memory_method": "Separate run: tracemalloc peak Python allocations (not process RSS)",
                                "quality_seed": 43})
    return results
