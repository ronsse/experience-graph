"""Retrieve routes -- search, packs, entities, traces."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from xpgraph.retrieve.pack_builder import PackBuilder
from xpgraph.retrieve.strategies import GraphSearch, KeywordSearch
from xpgraph.schemas.pack import PackBudget
from xpgraph.stores.base.event_log import EventType
from xpgraph_api.app import get_registry
from xpgraph_api.models import PackRequest, PackResponse

router = APIRouter()


@router.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    domain: str | None = Query(None, description="Domain filter"),
    limit: int = Query(20, description="Max results"),
) -> dict[str, Any]:
    """Full-text search across documents."""
    registry = get_registry()
    filters: dict[str, Any] = {}
    if domain:
        filters["domain"] = domain
    results = registry.document_store.search(q, limit=limit, filters=filters)
    return {"status": "ok", "query": q, "count": len(results), "results": results}


@router.post("/packs", response_model=PackResponse)
def assemble_pack(req: PackRequest) -> PackResponse:
    """Assemble a context pack."""
    registry = get_registry()

    builder = PackBuilder(strategies=[
        KeywordSearch(registry.document_store),
        GraphSearch(registry.graph_store),
    ])

    budget = PackBudget(max_items=req.max_items, max_tokens=req.max_tokens)
    pack = builder.build(
        intent=req.intent,
        domain=req.domain,
        agent_id=req.agent_id,
        budget=budget,
    )

    return PackResponse(
        pack_id=pack.pack_id,
        intent=pack.intent,
        domain=pack.domain,
        agent_id=pack.agent_id,
        count=len(pack.items),
        items=[item.model_dump() for item in pack.items],
        retrieval_report=pack.retrieval_report.model_dump(),
    )


@router.get("/entities/{entity_id}")
def get_entity(
    entity_id: str,
    depth: int = Query(1, description="Subgraph traversal depth"),
) -> dict[str, Any]:
    """Get an entity and its neighborhood."""
    registry = get_registry()
    node = registry.graph_store.get_node(entity_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    subgraph = registry.graph_store.get_subgraph(seed_ids=[entity_id], depth=depth)
    return {"status": "ok", "entity": node, "subgraph": subgraph}


@router.get("/traces")
def list_traces(
    domain: str | None = Query(None),
    agent: str | None = Query(None, alias="agent_id"),
    limit: int = Query(20),
) -> dict[str, Any]:
    """List recent traces."""
    registry = get_registry()
    traces = registry.trace_store.query(domain=domain, agent_id=agent, limit=limit)
    total = registry.trace_store.count(domain=domain)

    items = [
        {
            "trace_id": t.trace_id,
            "source": t.source.value,
            "intent": t.intent,
            "outcome": t.outcome.status.value if t.outcome else None,
            "domain": t.context.domain if t.context else None,
            "agent_id": t.context.agent_id if t.context else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in traces
    ]
    return {"status": "ok", "total": total, "count": len(items), "traces": items}


@router.get("/traces/{trace_id}")
def get_trace(trace_id: str) -> dict[str, Any]:
    """Get a specific trace by ID."""
    registry = get_registry()
    trace = registry.trace_store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
    return {"status": "ok", "trace": trace.model_dump(mode="json")}


@router.get("/precedents")
def list_precedents(
    domain: str | None = Query(None),
    limit: int = Query(20),
) -> dict[str, Any]:
    """List promoted precedents."""
    registry = get_registry()
    events = registry.event_log.get_events(
        event_type=EventType.PRECEDENT_PROMOTED,
        limit=limit,
    )
    if domain:
        events = [e for e in events if e.payload.get("domain") == domain]

    items = [
        {
            "event_id": e.event_id,
            "entity_id": e.entity_id,
            "title": e.payload.get("title", ""),
            "description": e.payload.get("description", ""),
            "domain": e.payload.get("domain"),
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in events
    ]
    return {"status": "ok", "count": len(items), "precedents": items}
