"""FastAPI application for Experience Graph."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from xpgraph.stores.registry import StoreRegistry

logger = structlog.get_logger(__name__)

_registry: StoreRegistry | None = None


def get_registry() -> StoreRegistry:
    """Get the global StoreRegistry."""
    if _registry is None:
        msg = "StoreRegistry not initialized. Start the app with create_app()."
        raise RuntimeError(msg)
    return _registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Initialize and tear down the StoreRegistry."""
    global _registry  # noqa: PLW0603
    _registry = StoreRegistry.from_config_dir()
    logger.info("api_stores_initialized")
    yield
    _registry.close()
    _registry = None
    logger.info("api_stores_closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from xpgraph_api.routes import admin, curate, ingest, retrieve  # noqa: PLC0415

    app = FastAPI(
        title="Experience Graph API",
        description="Structured memory and learning for AI agents",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
    app.include_router(retrieve.router, prefix="/api/v1", tags=["retrieve"])
    app.include_router(curate.router, prefix="/api/v1", tags=["curate"])

    return app


def main() -> None:
    """Run the API server."""
    import uvicorn  # noqa: PLC0415

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8420)  # noqa: S104


if __name__ == "__main__":
    main()
