"""FastAPI entry point for the Route Optimization Service (Task 1)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.route import router as route_router
from app.config.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Decision Support System (IDSS) - Route Optimization Service using BFS, Dijkstra, and A*.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(route_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root entry point providing service discovery and documentation links."""
    return {
        "service": settings.APP_NAME,
        "status": "running",
        "health": "/health",
        "documentation": "/docs",
        "cities_api": "/api/route/cities",
        "plan_api": "/api/route/plan",
        "compare_api": "/api/route/compare",
        "benchmark_api": "/api/route/benchmark",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is available."""
    return {"status": "ok", "service": "task1-route-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=True,
    )
