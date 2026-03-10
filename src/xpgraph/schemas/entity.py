"""Entity schema for Experience Graph."""

from __future__ import annotations

from pydantic import Field

from xpgraph.core.base import TimestampedModel, VersionedModel
from xpgraph.core.ids import generate_ulid
from xpgraph.schemas.enums import EntityType


class EntitySource(VersionedModel):
    """Origin information for an entity."""

    origin: str
    detail: str | None = None
    trace_id: str | None = None


class Entity(TimestampedModel, VersionedModel):
    """A named entity in the experience graph."""

    entity_id: str = Field(default_factory=generate_ulid)
    entity_type: EntityType
    name: str
    properties: dict = Field(default_factory=dict)
    source: EntitySource | None = None
    metadata: dict = Field(default_factory=dict)
