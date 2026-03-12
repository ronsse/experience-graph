"""Tests for the REST API routes."""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import xpgraph_api.app as app_module
from xpgraph.stores.registry import StoreRegistry
from xpgraph_api.routes import admin, curate, ingest, retrieve


@pytest.fixture
def client(tmp_path):
    """Create a test client with a temporary store."""
    registry = StoreRegistry(stores_dir=tmp_path / "stores")
    app_module._registry = registry

    # Build app without the default lifespan (which calls from_config_dir)
    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
    app.include_router(retrieve.router, prefix="/api/v1", tags=["retrieve"])
    app.include_router(curate.router, prefix="/api/v1", tags=["curate"])

    with TestClient(app) as c:
        yield c
    registry.close()
    app_module._registry = None


def _make_trace(intent="test task", domain=None, agent_id=None):
    """Build a minimal valid trace payload."""
    ctx = {}
    if domain:
        ctx["domain"] = domain
    if agent_id:
        ctx["agent_id"] = agent_id
    return {
        "source": "agent",
        "intent": intent,
        "steps": [],
        "context": ctx,
    }


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_stats_empty(client):
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["traces"] == 0
    assert data["documents"] == 0


def test_ingest_trace(client):
    trace = _make_trace()
    resp = client.post("/api/v1/traces", json=trace)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["trace_id"] is not None


def test_ingest_invalid_trace(client):
    resp = client.post("/api/v1/traces", json={"bad": "data"})
    assert resp.status_code == 422


def test_search_empty(client):
    resp = client.get("/api/v1/search", params={"q": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0


def test_list_traces(client):
    trace = _make_trace(intent="list test")
    client.post("/api/v1/traces", json=trace)

    resp = client.get("/api/v1/traces")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["traces"][0]["intent"] == "list test"


def test_get_trace_not_found(client):
    resp = client.get("/api/v1/traces/nonexistent")
    assert resp.status_code == 404


def test_get_trace_by_id(client):
    trace = _make_trace(intent="get by id")
    ingest_resp = client.post("/api/v1/traces", json=trace)
    trace_id = ingest_resp.json()["trace_id"]

    resp = client.get(f"/api/v1/traces/{trace_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace"]["intent"] == "get by id"


def test_create_entity(client):
    resp = client.post("/api/v1/entities", json={
        "entity_type": "concept",
        "name": "test entity",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["node_id"] is not None


def test_get_entity(client):
    resp = client.post("/api/v1/entities", json={
        "entity_type": "concept",
        "name": "test entity",
    })
    node_id = resp.json()["node_id"]

    resp = client.get(f"/api/v1/entities/{node_id}")
    assert resp.status_code == 200
    assert resp.json()["entity"]["node_id"] == node_id


def test_entity_not_found(client):
    resp = client.get("/api/v1/entities/nonexistent")
    assert resp.status_code == 404


def test_assemble_pack(client):
    resp = client.post("/api/v1/packs", json={
        "intent": "test pack",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["pack_id"] is not None
    assert data["intent"] == "test pack"


def test_stats_after_ingest(client):
    trace = _make_trace()
    client.post("/api/v1/traces", json=trace)

    resp = client.get("/api/v1/stats")
    data = resp.json()
    assert data["traces"] == 1


def test_precedents_empty(client):
    resp = client.get("/api/v1/precedents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
