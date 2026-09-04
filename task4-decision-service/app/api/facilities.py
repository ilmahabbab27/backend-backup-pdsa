"""CRUD endpoints for Task 4 public facilities."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.supabase_client import get_supabase

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


class FacilityPayload(BaseModel):
    location_key: str
    facility_type: str
    capacity: int | None = None
    current_load: int = 0
    priority_score: float = 0


def db_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if "foreign key" in message.lower() or "location" in message.lower():
        message = "Choose a location from the location list."
    return HTTPException(status_code=400, detail=message)


@router.get("/locations")
def list_locations() -> list[dict[str, Any]]:
    try:
        return get_supabase().table("locations").select("location_key,name").order("name").execute().data or []
    except Exception as exc:
        raise db_error(exc) from exc


@router.get("")
def list_facilities() -> list[dict[str, Any]]:
    try:
        return get_supabase().table("facilities").select("location_key,facility_type,capacity,current_load,priority_score").order("location_key").execute().data or []
    except Exception as exc:
        raise db_error(exc) from exc


@router.post("", status_code=201)
def create_facility(payload: FacilityPayload) -> dict[str, Any]:
    try:
        response = get_supabase().table("facilities").insert(payload.model_dump()).execute()
        return response.data[0]
    except Exception as exc:
        raise db_error(exc) from exc


@router.patch("/{location_key}")
def update_facility(location_key: str, payload: FacilityPayload) -> dict[str, Any]:
    try:
        response = get_supabase().table("facilities").update(payload.model_dump()).eq("location_key", location_key).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Facility was not found.")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise db_error(exc) from exc


@router.delete("/{location_key}")
def delete_facility(location_key: str) -> dict[str, str]:
    try:
        response = get_supabase().table("facilities").delete().eq("location_key", location_key).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Facility was not found.")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        raise db_error(exc) from exc
