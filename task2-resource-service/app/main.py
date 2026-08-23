"""FastAPI entry point for the Resource Allocation Service."""

from fastapi import FastAPI

app = FastAPI(title="Resource Allocation Service", version="0.1.0")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is available."""
    return {"status": "ok", "service": "task2-resource-service"}

