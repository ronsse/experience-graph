"""Ingest routes -- traces and evidence."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from xpgraph.errors import StoreError
from xpgraph.schemas.evidence import Evidence
from xpgraph.schemas.trace import Trace
from xpgraph_api.app import get_registry
from xpgraph_api.models import IngestResponse

router = APIRouter()


@router.post("/traces", response_model=IngestResponse)
def ingest_trace(body: dict[str, Any]) -> IngestResponse:
    """Ingest a trace."""
    try:
        trace = Trace.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid trace: {exc}") from exc

    registry = get_registry()
    try:
        trace_id = registry.trace_store.append(trace)
    except StoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return IngestResponse(trace_id=trace_id)


@router.post("/evidence", response_model=IngestResponse)
def ingest_evidence(body: dict[str, Any]) -> IngestResponse:
    """Ingest evidence."""
    try:
        evidence = Evidence.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid evidence: {exc}") from exc

    registry = get_registry()
    registry.document_store.put(
        doc_id=evidence.evidence_id,
        content=evidence.content or "",
        metadata={
            "evidence_type": evidence.evidence_type,
            "source_origin": evidence.source_origin,
        },
    )

    return IngestResponse(evidence_id=evidence.evidence_id)
