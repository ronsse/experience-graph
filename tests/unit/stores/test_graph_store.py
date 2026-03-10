"""Tests for GraphStore ABC and SQLiteGraphStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from xpgraph.stores.graph import SQLiteGraphStore


@pytest.fixture
def graph_store(tmp_path: Path):
    store = SQLiteGraphStore(tmp_path / "graph.db")
    yield store
    store.close()


def test_upsert_and_get_node(graph_store):
    nid = graph_store.upsert_node(None, "service", {"name": "auth"})
    node = graph_store.get_node(nid)
    assert node is not None
    assert node["node_type"] == "service"
    assert node["properties"]["name"] == "auth"


def test_upsert_node_with_explicit_id(graph_store):
    graph_store.upsert_node("n1", "person", {"name": "Alice"})
    node = graph_store.get_node("n1")
    assert node is not None
    assert node["properties"]["name"] == "Alice"


def test_update_node(graph_store):
    graph_store.upsert_node("n1", "service", {"v": 1})
    graph_store.upsert_node("n1", "service", {"v": 2})
    node = graph_store.get_node("n1")
    assert node is not None
    assert node["properties"]["v"] == 2


def test_upsert_and_get_edge(graph_store):
    graph_store.upsert_node("a", "service", {})
    graph_store.upsert_node("b", "service", {})
    eid = graph_store.upsert_edge("a", "b", "depends_on", {"weight": 1.0})
    edges = graph_store.get_edges("a", direction="outgoing")
    assert len(edges) == 1
    assert edges[0]["edge_type"] == "depends_on"
    assert edges[0]["edge_id"] == eid


def test_get_edges_incoming(graph_store):
    graph_store.upsert_node("a", "s", {})
    graph_store.upsert_node("b", "s", {})
    graph_store.upsert_edge("a", "b", "links_to")
    edges = graph_store.get_edges("b", direction="incoming")
    assert len(edges) == 1


def test_get_edges_both(graph_store):
    graph_store.upsert_node("a", "s", {})
    graph_store.upsert_node("b", "s", {})
    graph_store.upsert_node("c", "s", {})
    graph_store.upsert_edge("a", "b", "links_to")
    graph_store.upsert_edge("c", "b", "links_to")
    edges = graph_store.get_edges("b", direction="both")
    assert len(edges) == 2


def test_get_subgraph(graph_store):
    graph_store.upsert_node("a", "s", {})
    graph_store.upsert_node("b", "s", {})
    graph_store.upsert_node("c", "s", {})
    graph_store.upsert_edge("a", "b", "links_to")
    graph_store.upsert_edge("b", "c", "links_to")
    sg = graph_store.get_subgraph(["a"], depth=2)
    assert len(sg["nodes"]) == 3
    assert len(sg["edges"]) == 2


def test_query_by_type(graph_store):
    graph_store.upsert_node(None, "service", {"name": "a"})
    graph_store.upsert_node(None, "person", {"name": "b"})
    results = graph_store.query(node_type="service")
    assert len(results) == 1


def test_query_by_properties(graph_store):
    graph_store.upsert_node(None, "service", {"team": "platform"})
    graph_store.upsert_node(None, "service", {"team": "data"})
    results = graph_store.query(properties={"team": "platform"})
    assert len(results) == 1


def test_delete_node_cascades(graph_store):
    graph_store.upsert_node("a", "s", {})
    graph_store.upsert_node("b", "s", {})
    graph_store.upsert_edge("a", "b", "links")
    assert graph_store.delete_node("a") is True
    assert graph_store.get_node("a") is None
    assert graph_store.get_edges("b") == []


def test_delete_edge(graph_store):
    graph_store.upsert_node("a", "s", {})
    graph_store.upsert_node("b", "s", {})
    eid = graph_store.upsert_edge("a", "b", "links")
    assert graph_store.delete_edge(eid) is True
    assert graph_store.get_edges("a") == []


def test_get_nodes_bulk(graph_store):
    graph_store.upsert_node("a", "s", {"n": 1})
    graph_store.upsert_node("b", "s", {"n": 2})
    graph_store.upsert_node("c", "s", {"n": 3})
    nodes = graph_store.get_nodes_bulk(["a", "c"])
    assert len(nodes) == 2


def test_count(graph_store):
    assert graph_store.count_nodes() == 0
    graph_store.upsert_node(None, "s", {})
    assert graph_store.count_nodes() == 1
    assert graph_store.count_edges() == 0


def test_get_nonexistent(graph_store):
    assert graph_store.get_node("nope") is None


def test_delete_nonexistent(graph_store):
    assert graph_store.delete_node("nope") is False
    assert graph_store.delete_edge("nope") is False
