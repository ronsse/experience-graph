"""Tests for response formatters."""

from __future__ import annotations

from xpgraph.retrieve.formatters import (
    format_entities_as_markdown,
    format_lessons_as_markdown,
    format_pack_as_markdown,
    format_subgraph_as_markdown,
    format_traces_as_markdown,
)


def test_format_pack_empty():
    result = format_pack_as_markdown([], "test intent")
    assert "test intent" in result


def test_format_pack_with_items():
    items = [
        {
            "item_id": "id1",
            "item_type": "document",
            "excerpt": "hello world",
            "relevance_score": 0.9,
        },
        {
            "item_id": "id2",
            "item_type": "entity",
            "excerpt": "test entity",
            "relevance_score": 0.5,
        },
    ]
    result = format_pack_as_markdown(items, "test search", max_tokens=2000)
    assert "test search" in result
    assert "hello world" in result
    assert "document" in result


def test_format_pack_respects_token_budget():
    items = [
        {
            "item_id": f"id{i}",
            "item_type": "doc",
            "excerpt": "x" * 500,
            "relevance_score": 0.5,
        }
        for i in range(20)
    ]
    result = format_pack_as_markdown(items, "test", max_tokens=200)
    assert "omitted" in result


def test_format_traces_empty():
    assert "No traces" in format_traces_as_markdown([])


def test_format_traces_with_data():
    traces = [
        {
            "intent": "deploy service",
            "outcome": "success",
            "domain": "platform",
            "created_at": "2026-01-15T00:00:00",
        },
    ]
    result = format_traces_as_markdown(traces)
    assert "deploy service" in result
    assert "success" in result


def test_format_entities_empty():
    assert "No entities" in format_entities_as_markdown([])


def test_format_entities_with_data():
    entities = [
        {
            "node_id": "n1",
            "node_type": "concept",
            "properties": {"name": "Redis", "description": "Cache layer"},
        },
    ]
    result = format_entities_as_markdown(entities)
    assert "Redis" in result
    assert "concept" in result


def test_format_lessons_empty():
    assert "No lessons" in format_lessons_as_markdown([])


def test_format_lessons_with_data():
    lessons = [
        {
            "title": "Always check locks",
            "description": "Deadlocks are bad",
            "domain": "platform",
        },
    ]
    result = format_lessons_as_markdown(lessons)
    assert "Always check locks" in result
    assert "Deadlocks" in result


def test_format_subgraph():
    entity = {
        "node_id": "n1",
        "node_type": "service",
        "properties": {"name": "API Gateway"},
    }
    subgraph = {
        "nodes": [
            entity,
            {
                "node_id": "n2",
                "node_type": "service",
                "properties": {"name": "Auth"},
            },
        ],
        "edges": [
            {
                "source_id": "n1",
                "target_id": "n2",
                "edge_type": "depends_on",
            },
        ],
    }
    result = format_subgraph_as_markdown(entity, subgraph)
    assert "API Gateway" in result
    assert "depends_on" in result
    assert "Auth" in result
