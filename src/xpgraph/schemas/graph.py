"""Graph edge schema for Experience Graph."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from xpgraph.core.base import TimestampedModel, VersionedModel
from xpgraph.core.ids import generate_ulid
from xpgraph.schemas.enums import EdgeKind


class Edge(TimestampedModel, VersionedModel):
    """A directed edge in the experience graph."""

    edge_id: str = Field(default_factory=generate_ulid)
    source_id: str
    target_id: str
    edge_kind: EdgeKind
    properties: dict[str, Any] = Field(default_factory=dict)
