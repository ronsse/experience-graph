"""Curate routes -- promote, link, label, feedback, entity creation."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from xpgraph.mutate.commands import Command, CommandStatus, Operation
from xpgraph.mutate.executor import MutationExecutor
from xpgraph.stores.base.event_log import EventType
from xpgraph_api.app import get_registry
from xpgraph_api.models import (
    CommandResponse,
    EntityCreateRequest,
    FeedbackRequest,
    LinkRequest,
    PromoteRequest,
)

router = APIRouter()


def _execute_command(cmd: Command) -> CommandResponse:
    """Execute a command through the mutation pipeline."""
    registry = get_registry()
    executor = MutationExecutor(event_log=registry.event_log)
    result = executor.execute(cmd)
    if result.status == CommandStatus.FAILED:
        raise HTTPException(status_code=400, detail=result.message)
    return CommandResponse(
        status=result.status.value,
        command_id=result.command_id,
        operation=result.operation,
        message=result.message,
        created_id=result.created_id,
    )


@router.post("/precedents", response_model=CommandResponse)
def promote(req: PromoteRequest) -> CommandResponse:
    """Promote a trace to a precedent."""
    cmd = Command(
        operation=Operation.PRECEDENT_PROMOTE,
        args={
            "trace_id": req.trace_id,
            "title": req.title,
            "description": req.description,
        },
        target_id=req.trace_id,
        target_type="trace",
        requested_by=req.requested_by,
    )
    return _execute_command(cmd)


@router.post("/links")
def create_link(req: LinkRequest) -> dict[str, Any]:
    """Create a graph edge between two entities."""
    registry = get_registry()
    store = registry.graph_store

    if store.get_node(req.source_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Source not found: {req.source_id}"
        )
    if store.get_node(req.target_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Target not found: {req.target_id}"
        )

    edge_id = store.upsert_edge(
        source_id=req.source_id,
        target_id=req.target_id,
        edge_type=req.edge_kind,
        properties=req.properties,
    )
    return {
        "status": "ok",
        "edge_id": edge_id,
        "source_id": req.source_id,
        "target_id": req.target_id,
    }


@router.post("/entities")
def create_entity(req: EntityCreateRequest) -> dict[str, Any]:
    """Create an entity node in the knowledge graph."""
    registry = get_registry()
    props = dict(req.properties)
    props["name"] = req.name

    node_id = registry.graph_store.upsert_node(
        node_id=None,
        node_type=req.entity_type,
        properties=props,
    )
    return {
        "status": "ok",
        "node_id": node_id,
        "entity_type": req.entity_type,
        "name": req.name,
    }


@router.post("/feedback", response_model=CommandResponse)
def record_feedback(req: FeedbackRequest) -> CommandResponse:
    """Record feedback on a trace or precedent."""
    args: dict[str, object] = {"target_id": req.target_id, "rating": req.rating}
    if req.comment:
        args["comment"] = req.comment
    if req.pack_id:
        args["pack_id"] = req.pack_id
    cmd = Command(
        operation=Operation.FEEDBACK_RECORD,
        args=args,
        target_id=req.target_id,
        requested_by="api",
    )
    return _execute_command(cmd)


@router.post("/packs/{pack_id}/feedback")
def pack_feedback(
    pack_id: str,
    success: bool = Query(..., description="Whether the context was helpful"),
    notes: str | None = Query(None, description="Optional notes"),
) -> dict[str, Any]:
    """Record feedback on a specific context pack."""
    registry = get_registry()
    registry.event_log.emit(
        EventType.FEEDBACK_RECORDED,
        source="api",
        entity_id=pack_id,
        entity_type="pack",
        payload={
            "pack_id": pack_id,
            "success": success,
            "notes": notes or "",
            "rating": 1.0 if success else 0.0,
        },
    )
    return {"status": "ok", "pack_id": pack_id, "feedback": "positive" if success else "negative"}
