"""Precedent schema for Experience Graph."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from xpgraph.core.base import TimestampedModel, VersionedModel
from xpgraph.core.ids import generate_ulid
from xpgraph.schemas.trace import Feedback


class Precedent(TimestampedModel, VersionedModel):
    """A reusable precedent distilled from one or more traces."""

    precedent_id: str = Field(default_factory=generate_ulid)
    source_trace_ids: list[str] = Field(default_factory=list)
    title: str
    description: str
    pattern: str | None = None
    applicability: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    promoted_by: str
    evidence_refs: list[str] = Field(default_factory=list)
    feedback: list[Feedback] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
