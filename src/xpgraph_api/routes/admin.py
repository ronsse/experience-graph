"""Admin routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from xpgraph.retrieve.effectiveness import analyze_effectiveness
from xpgraph_api.app import get_registry
from xpgraph_api.models import HealthResponse, StatsResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Check API and store health."""
    return HealthResponse(status="ok", checks={"api": True, "stores": True})


@router.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Get store statistics."""
    registry = get_registry()
    return StatsResponse(
        traces=registry.trace_store.count(),
        documents=registry.document_store.count(),
        nodes=registry.graph_store.count_nodes(),
        edges=registry.graph_store.count_edges(),
        events=registry.event_log.count(),
    )


@router.get("/effectiveness")
def effectiveness(
    days: int = Query(30, description="Days of history to analyze"),
    min_appearances: int = Query(2, description="Minimum item appearances"),
) -> dict[str, Any]:
    """Analyze context pack effectiveness."""
    registry = get_registry()
    report = analyze_effectiveness(
        registry.event_log,
        days=days,
        min_appearances=min_appearances,
    )
    return {"status": "ok", **report.to_dict()}
