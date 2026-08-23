"""FastAPI entry point for the Route Optimization Service."""

from fastapi import FastAPI

app = FastAPI(title="Route Optimization Service", version="0.1.0")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is available."""
    return {"status": "ok", "service": "task1-route-service"}

