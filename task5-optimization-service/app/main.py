"""FastAPI Application Entrypoint for Smart City Waste Collection Optimization Service."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import time
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_map_repository
from app.api.v1.router import api_router
from app.config.settings import get_settings
from app.models.schemas import HealthResponse, StructuredErrorResponse
from app.utils.exceptions import OptimizationException
from app.utils.logger import log_error, log_request, log_response, log_startup_banner

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for startup banner and resource pre-initialization."""
    try:
        map_repo = get_map_repository()
        nodes = map_repo.get_node_dict()
        node_counts = {
            "start": len(map_repo.get_nodes_by_type("start")),
            "destination": len(map_repo.get_nodes_by_type("destination")),
            "bin": len(map_repo.get_nodes_by_type("bin")),
            "intersection": len(map_repo.get_nodes_by_type("intersection")),
        }
        total_waste = sum(n.weight_kg for n in map_repo.get_nodes_by_type("bin"))
        edge_count = map_repo.get_graph().number_of_edges()

        log_startup_banner(
            app_name=settings.APP_NAME,
            port=settings.APP_PORT,
            map_path=str(settings.resolved_map_data_path),
            node_counts=node_counts,
            edge_count=edge_count,
            total_waste_kg=total_waste,
        )
    except Exception as e:
        print(f"[STARTUP WARNING] Could not pre-load map data: {e}", flush=True)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-ready backend service solving homogeneous waste collection fleet "
        "allocation, sequencing, and route optimization using NetworkX, Dijkstra's algorithm, "
        "and Branch and Bound pruning."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers
@app.exception_handler(OptimizationException)
async def optimization_exception_handler(request: Request, exc: OptimizationException) -> JSONResponse:
    """Handle domain-specific optimization errors with structured recovery suggestions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": exc.error_type,
            "message": exc.message,
            "detail": exc.message,
            "details": exc.details,
            "suggestions": exc.suggestions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Standardize HTTP exception responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": "HTTPException",
            "message": str(exc.detail),
            "detail": str(exc.detail),
            "details": {},
            "suggestions": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unexpected server exception handler."""
    log_error("Unhandled Internal Server Error", str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "error": "InternalServerError",
            "message": "An unexpected error occurred during optimization processing.",
            "detail": str(exc),
            "details": {},
            "suggestions": ["Please check server logs or verify map and fleet parameter configuration."],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Response:
    """Middleware to log all incoming HTTP requests and their processing times."""
    start_time = time.perf_counter()
    client_host = request.client.host if request.client else "unknown"
    log_request(request.method, request.url.path, client_host)

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    log_response(request.method, request.url.path, response.status_code, duration_ms)
    return response


# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def root_health() -> HealthResponse:
    """Root health check endpoint."""
    return HealthResponse(
        status="ok",
        service="task5-optimization-service",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=True,
    )
