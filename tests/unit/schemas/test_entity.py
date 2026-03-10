"""Tests for entity schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from xpgraph.schemas.entity import Entity, EntitySource
from xpgraph.schemas.enums import EntityType


class TestEntityDefaults:
    """Entity creates with sensible defaults."""

    def test_minimal_entity(self) -> None:
        entity = Entity(
            entity_type=EntityType.PERSON,
            name="Alice",
        )
        assert entity.entity_id  # ULID generated
        assert len(entity.entity_id) == 26
        assert entity.entity_type == EntityType.PERSON
        assert entity.name == "Alice"
        assert entity.properties == {}
        assert entity.source is None
        assert entity.metadata == {}
        assert entity.created_at is not None
        assert entity.updated_at is not None
        assert entity.schema_version == "0.1.0"


class TestEntityWithPropertiesAndSource:
    """Entity with properties and source."""

    def test_entity_with_properties_and_source(self) -> None:
        src = EntitySource(
            origin="import",
            detail="CSV row 42",
            trace_id="trace-abc",
        )
        entity = Entity(
            entity_type=EntityType.SERVICE,
            name="auth-service",
            properties={"url": "https://auth.example.com", "version": "2.1"},
            source=src,
            metadata={"imported": True},
        )
        assert entity.entity_type == EntityType.SERVICE
        assert entity.properties["url"] == "https://auth.example.com"
        assert entity.source is not None
        assert entity.source.origin == "import"
        assert entity.source.detail == "CSV row 42"
        assert entity.source.trace_id == "trace-abc"
        assert entity.metadata == {"imported": True}

    def test_entity_source_minimal(self) -> None:
        src = EntitySource(origin="manual")
        assert src.origin == "manual"
        assert src.detail is None
        assert src.trace_id is None


class TestEntityForbidsExtras:
    """Entity rejects unknown fields."""

    def test_entity_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            Entity(
                entity_type=EntityType.TOOL,
                name="hammer",
                nope="bad",  # type: ignore[call-arg]
            )

    def test_entity_source_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            EntitySource(
                origin="x",
                bad_field=1,  # type: ignore[call-arg]
            )
