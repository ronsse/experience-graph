"""Shared enums for Experience Graph schemas."""

from __future__ import annotations

from enum import StrEnum


class TraceSource(StrEnum):
    AGENT = "agent"
    HUMAN = "human"
    WORKFLOW = "workflow"
    SYSTEM = "system"


class OutcomeStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    PERSON = "person"
    SYSTEM = "system"
    SERVICE = "service"
    TEAM = "team"
    DOCUMENT = "document"
    CONCEPT = "concept"
    DOMAIN = "domain"
    FILE = "file"
    PROJECT = "project"
    TOOL = "tool"


class EvidenceType(StrEnum):
    DOCUMENT = "document"
    SNIPPET = "snippet"
    LINK = "link"
    CONFIG = "config"
    IMAGE = "image"
    FILE_POINTER = "file_pointer"


class PolicyType(StrEnum):
    MUTATION = "mutation"
    ACCESS = "access"
    RETENTION = "retention"
    REDACTION = "redaction"


class Enforcement(StrEnum):
    ENFORCE = "enforce"
    WARN = "warn"
    AUDIT_ONLY = "audit_only"


class EdgeKind(StrEnum):
    # Trace relationships
    TRACE_USED_EVIDENCE = "trace_used_evidence"
    TRACE_PRODUCED_ARTIFACT = "trace_produced_artifact"
    TRACE_TOUCHED_ENTITY = "trace_touched_entity"
    TRACE_PROMOTED_TO_PRECEDENT = "trace_promoted_to_precedent"
    # Entity relationships
    ENTITY_RELATED_TO = "entity_related_to"
    ENTITY_PART_OF = "entity_part_of"
    ENTITY_DEPENDS_ON = "entity_depends_on"
    # Evidence relationships
    EVIDENCE_ATTACHED_TO = "evidence_attached_to"
    EVIDENCE_SUPPORTS = "evidence_supports"
    # Precedent relationships
    PRECEDENT_APPLIES_TO = "precedent_applies_to"
    PRECEDENT_DERIVED_FROM = "precedent_derived_from"
