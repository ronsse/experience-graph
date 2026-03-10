"""Policy schema for Experience Graph."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from xpgraph.core.base import TimestampedModel, VersionedModel
from xpgraph.core.ids import generate_ulid
from xpgraph.schemas.enums import Enforcement, PolicyType


class PolicyScope(VersionedModel):
    """Scope at which a policy applies."""

    level: str  # global, domain, team, entity_type
    value: str | None = None


class PolicyRule(VersionedModel):
    """A single rule within a policy."""

    operation: str  # e.g. "precedent.promote", "*"
    condition: str = "always"
    action: str = "allow"  # allow, deny, require_approval, warn
    params: dict[str, Any] = Field(default_factory=dict)


class Policy(TimestampedModel, VersionedModel):
    """A governance policy controlling operations in the experience graph."""

    policy_id: str = Field(default_factory=generate_ulid)
    policy_type: PolicyType
    scope: PolicyScope
    rules: list[PolicyRule] = Field(default_factory=list)
    enforcement: Enforcement = Enforcement.ENFORCE
    metadata: dict[str, Any] = Field(default_factory=dict)
