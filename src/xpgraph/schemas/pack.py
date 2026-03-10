"""Pack schema for Experience Graph."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from xpgraph.core.base import TimestampedModel, VersionedModel, utc_now
from xpgraph.core.ids import generate_ulid


class PackItem(VersionedModel):
    """A single item included in a context pack."""

    item_id: str
    item_type: str  # trace, evidence, precedent, entity
    excerpt: str = ""
    relevance_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackBudget(VersionedModel):
    """Budget constraints for a context pack."""

    max_items: int = 50
    max_tokens: int = 8000


class RetrievalReport(VersionedModel):
    """Report on how pack items were retrieved."""

    queries_run: int = 0
    candidates_found: int = 0
    items_selected: int = 0
    duration_ms: int = 0
    strategies_used: list[str] = Field(default_factory=list)


class Pack(TimestampedModel, VersionedModel):
    """A context pack assembled for an agent or workflow."""

    pack_id: str = Field(default_factory=generate_ulid)
    intent: str
    items: list[PackItem] = Field(default_factory=list)
    retrieval_report: RetrievalReport = Field(default_factory=RetrievalReport)
    policies_applied: list[str] = Field(default_factory=list)
    budget: PackBudget = Field(default_factory=PackBudget)
    domain: str | None = None
    agent_id: str | None = None
    assembled_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
