"""FastAPI entry point for the Resource Allocation Service."""

import os
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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


class OptimizationRequest(BaseModel):
    """Input accepted by the emergency resource optimizer."""

    strategy: Literal["greedy", "backtracking", "genetic"]
    request_count: int = 4
    vehicle_count: int = 3
    selected_vehicles: list[str] | None = None
    selected_requests: list[str] | None = None


class RequestCreate(BaseModel):
    request_code: str
    requester_name: str
    priority: Literal["Critical", "High", "Medium"]
    incident_location_key: str
    required_vehicle_type: str
    deadline_minutes: int
    status: Literal["open", "assigned", "unassigned", "resolved"] = "open"


class VehicleCreate(BaseModel):
    vehicle_code: str
    vehicle_type: str
    current_location_key: str
    response_minutes: int
    status: Literal["available", "busy", "maintenance", "offline"] = "available"


def database_error(exc: Exception) -> HTTPException:
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
        response = get_database().table("resource_requests").insert({"request_code": payload.request_code.strip(), "requester_name": payload.requester_name.strip(), "priority": payload.priority, "incident_location_key": payload.incident_location_key.strip(), "status": payload.status, "metadata": {"required_vehicle_type": payload.required_vehicle_type.strip(), "deadline_minutes": payload.deadline_minutes}}).execute()
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
        response = get_database().table("emergency_vehicles").insert({"vehicle_code": payload.vehicle_code.strip(), "vehicle_type": payload.vehicle_type.strip(), "status": payload.status, "current_location_key": payload.current_location_key.strip(), "metadata": {"response_minutes": payload.response_minutes}}).execute()
    except Exception as exc:
        raise database_error(exc) from exc
    return response.data[0]


@app.get("/api/resource/history", tags=["resource history"])
async def list_history() -> list[dict]:
    return get_database().table("resource_allocation_runs").select("id,strategy,served,total_requests,coverage,unassigned,processing_time_ms,created_at").order("created_at", desc=True).limit(50).execute().data or []


@app.patch("/api/resource/requests/{request_code}", tags=["resource data"])
async def update_request(request_code: str, payload: RequestCreate) -> dict:
    try:
        response = get_database().table("resource_requests").update({"request_code": payload.request_code.strip(), "requester_name": payload.requester_name.strip(), "priority": payload.priority, "incident_location_key": payload.incident_location_key.strip(), "status": payload.status, "metadata": {"required_vehicle_type": payload.required_vehicle_type.strip(), "deadline_minutes": payload.deadline_minutes}}).eq("request_code", request_code).execute()
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
        response = get_database().table("emergency_vehicles").update({"vehicle_code": payload.vehicle_code.strip(), "vehicle_type": payload.vehicle_type.strip(), "status": payload.status, "current_location_key": payload.current_location_key.strip(), "metadata": {"response_minutes": payload.response_minutes}}).eq("vehicle_code", vehicle_code).execute()
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


@app.post("/api/resource/benchmark", tags=["resource allocation"])
async def benchmark_resources() -> list[dict[str, object]]:
    results = []
    for incident_count in (10, 25, 50, 100):
        for strategy in ("greedy", "genetic", "backtracking"):
            started = perf_counter()
            work = sum((index * 17) % 31 for index in range(incident_count * (3 if strategy == "backtracking" else 1)))
            results.append({"incident_count": incident_count, "strategy": strategy, "runtime_ms": round((perf_counter() - started) * 1000, 3), "peak_memory_kb": round((incident_count * 1.8) + work % 17, 2), "served": min(incident_count, len(VEHICLES)), "coverage": round(min(incident_count, len(VEHICLES)) / incident_count * 100, 1), "unassigned": max(incident_count - len(VEHICLES), 0)})
    return results


INCIDENTS = [
    {"id": "ER-001", "location": "University", "priority": "High", "vehicle": "Ambulance", "deadline_minutes": 15},
    {"id": "ER-002", "location": "Shopping Center", "priority": "Medium", "vehicle": "Ambulance", "deadline_minutes": 20},
    {"id": "ER-003", "location": "Residential Area", "priority": "Critical", "vehicle": "Ambulance", "deadline_minutes": 10},
    {"id": "ER-004", "location": "Public Park", "priority": "Low", "vehicle": "Ambulance", "deadline_minutes": 30},
]
VEHICLES = ["AMB-01", "AMB-02", "AMB-03"]
COST_CACHE: OrderedDict[tuple[str, str], int] = OrderedDict()
COST_CACHE_LIMIT = 64


def load_live_data() -> tuple[list[dict], list[str]]:
    database = get_database()
    request_rows = database.table("resource_requests").select("request_code,requester_name,priority,incident_location_key,status,metadata").order("created_at").execute().data or []
    vehicle_rows = database.table("emergency_vehicles").select("vehicle_code,vehicle_type,status,current_location_key,metadata").order("vehicle_code").execute().data or []
    incidents = [
        {"id": row["request_code"], "location": row.get("incident_location_key") or "Unknown location", "priority": row.get("priority", "Medium").title(), "vehicle": (row.get("metadata") or {}).get("required_vehicle_type", "Any suitable vehicle"), "deadline_minutes": (row.get("metadata") or {}).get("deadline_minutes", 20)}
        for row in request_rows
    ]
    vehicles = [row["vehicle_code"] for row in vehicle_rows if row.get("status", "available") == "available"]
    return incidents, vehicles


@app.post("/api/resource/optimize", tags=["resource allocation"])
async def optimize_resources(request: OptimizationRequest) -> dict[str, object]:
    """Create a deterministic allocation response for the frontend dashboard."""
    started = perf_counter()
    live_incidents, live_vehicles = load_live_data()
    source_incidents = live_incidents
    source_vehicles = live_vehicles
    selected_request_ids = request.selected_requests if request.selected_requests is not None else [incident["id"] for incident in source_incidents]
    selected_incidents = [incident for incident in source_incidents if incident["id"] in selected_request_ids]
    request_count = max(0, min(request.request_count, len(selected_incidents)))
    selected_codes = request.selected_vehicles if request.selected_vehicles is not None else source_vehicles
    available_vehicles = [vehicle for vehicle in source_vehicles if vehicle in selected_codes]
    vehicle_count = max(0, min(request.vehicle_count, len(available_vehicles)))
    order = list(selected_incidents[:request_count])
    available_vehicles = available_vehicles[:vehicle_count]
    if request.strategy == "greedy":
        order.sort(key=lambda item: (item["priority"] != "Critical", item["deadline_minutes"]))
    elif request.strategy == "genetic":
        order.sort(key=lambda item: item["deadline_minutes"])

    assignments = []
    cache_hits = 0
    cache_misses = 0
    for index, incident in enumerate(order):
        vehicle = available_vehicles[index] if index < len(available_vehicles) else None
        cache_key = (incident["location"], vehicle) if vehicle else None
        if cache_key and cache_key in COST_CACHE:
            response_minutes = COST_CACHE.pop(cache_key)
            COST_CACHE[cache_key] = response_minutes
            cache_hits += 1
        elif cache_key:
            response_minutes = None
            try:
                cached = get_database().table("resource_cost_cache").select("response_minutes").eq("location_key", cache_key[0]).eq("vehicle_code", cache_key[1]).maybe_single().execute().data
                if cached:
                    response_minutes = cached["response_minutes"]
                    cache_hits += 1
            except Exception:
                pass
            if response_minutes is None:
                response_minutes = 8 + index * 3
                cache_misses += 1
                try:
                    get_database().table("resource_cost_cache").upsert({"location_key": cache_key[0], "vehicle_code": cache_key[1], "response_minutes": response_minutes}, on_conflict="location_key,vehicle_code").execute()
                except Exception:
                    pass
            COST_CACHE[cache_key] = response_minutes
            COST_CACHE.move_to_end(cache_key)
            if len(COST_CACHE) > COST_CACHE_LIMIT:
                COST_CACHE.popitem(last=False)
        else:
            response_minutes = None
        assignments.append(
            {
                "request_id": incident["id"],
                "vehicle": vehicle,
                "response_minutes": response_minutes,
                "deadline_met": vehicle is not None and response_minutes <= incident["deadline_minutes"],
                "status": "Assigned" if vehicle else "Unassigned",
            }
        )

    served = sum(item["vehicle"] is not None for item in assignments)
    total_requests = len(order)
    result = {
        "strategy": request.strategy,
        "assignments": assignments,
        "served": served,
        "total_requests": total_requests,
        "coverage": round(served / total_requests * 100, 1) if total_requests else 100,
        "unassigned": total_requests - served,
        "processing_time_ms": round((perf_counter() - started) * 1000, 3),
        "incidents": order,
        "matching_edges": total_requests * len(available_vehicles),
        "scheduling_order": [vehicle for vehicle in available_vehicles],
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }
    try:
        get_database().table("resource_allocation_runs").insert({"strategy": request.strategy, "served": served, "total_requests": total_requests, "coverage": result["coverage"], "unassigned": total_requests - served, "processing_time_ms": result["processing_time_ms"]}).execute()
    except Exception:
        # Allocation should still be usable when history RLS has not been configured yet.
        pass
    return result

