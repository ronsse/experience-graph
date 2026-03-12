"""API request and response models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# -- Generic responses --


class StatusResponse(BaseModel):
    """Generic success response."""

    status: str = "ok"
    message: str | None = None


class ErrorResponse(BaseModel):
    """Generic error response."""

    status: str = "error"
    message: str
    code: str | None = None


# -- Ingest --


class IngestResponse(BaseModel):
    """Response after ingesting a trace or evidence."""

    status: str = "ok"
    trace_id: str | None = None
    evidence_id: str | None = None


# -- Retrieve --


class SearchRequest(BaseModel):
    """Full-text search request."""

    q: str
    domain: str | None = None
    limit: int = 20


class PackRequest(BaseModel):
    """Request to assemble a context pack."""

    intent: str
    domain: str | None = None
    agent_id: str | None = None
    max_items: int = 50
    max_tokens: int = 8000


class PackResponse(BaseModel):
    """Response containing an assembled context pack."""

    status: str = "ok"
    pack_id: str
    intent: str
    domain: str | None = None
    agent_id: str | None = None
    count: int
    items: list[dict[str, Any]]
    retrieval_report: dict[str, Any] | None = None


# -- Curate --


class PromoteRequest(BaseModel):
    """Request to promote a trace to a precedent."""

    trace_id: str
    title: str
    description: str
    requested_by: str = "api"


class LinkRequest(BaseModel):
    """Request to create a graph edge."""

    source_id: str
    target_id: str
    edge_kind: str = "entity_related_to"
    properties: dict[str, Any] | None = None


class EntityCreateRequest(BaseModel):
    """Request to create an entity node."""

    entity_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    """Request to record feedback on a target."""

    target_id: str
    rating: float
    comment: str | None = None
    pack_id: str | None = None  # Link feedback to a context pack


class CommandResponse(BaseModel):
    """Response after executing a mutation command."""

    status: str
    command_id: str
    operation: str
    message: str
    created_id: str | None = None


# -- Admin --


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    checks: dict[str, bool] = Field(default_factory=dict)


class StatsResponse(BaseModel):
    """Store statistics response."""

    status: str = "ok"
    traces: int = 0
    documents: int = 0
    nodes: int = 0
    edges: int = 0
    events: int = 0
