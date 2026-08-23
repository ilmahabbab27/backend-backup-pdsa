"""FastAPI entry point for the Network Analysis Service."""

from fastapi import FastAPI

app = FastAPI(title="Network Analysis Service", version="0.1.0")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is available."""
    return {"status": "ok", "service": "task3-network-service"}

