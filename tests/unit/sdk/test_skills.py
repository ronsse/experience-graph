"""Tests for SDK skill functions."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from xpgraph_sdk.client import XPGClient
from xpgraph_sdk.skills import (
    get_context_for_task,
    get_latest_successful_trace,
    get_recent_activity,
    save_trace_and_extract_lessons,
)


@pytest.fixture
def client(tmp_path: Path):
    os.environ["XPG_CONFIG_DIR"] = str(tmp_path / "config")
    os.environ["XPG_DATA_DIR"] = str(tmp_path / "data")
    (tmp_path / "data" / "stores").mkdir(parents=True)
    c = XPGClient()
    yield c
    c.close()
    del os.environ["XPG_DATA_DIR"]
    del os.environ["XPG_CONFIG_DIR"]


def test_get_context_for_task_empty(client):
    result = get_context_for_task(client, "test intent")
    assert isinstance(result, str)
    assert "test intent" in result.lower() or "no relevant" in result.lower()


def test_get_latest_successful_trace_none(client):
    result = get_latest_successful_trace(client, "deploy")
    assert "No successful traces" in result


def test_save_trace_and_extract_lessons(client):
    trace = {
        "source": "agent",
        "intent": "deploy service",
        "steps": [],
        "outcome": {"status": "success"},
        "context": {"agent_id": "test", "domain": "test"},
    }
    result = save_trace_and_extract_lessons(client, trace)
    assert "ingested" in result.lower()
    assert "deploy service" in result


def test_get_recent_activity_empty(client):
    result = get_recent_activity(client)
    assert "No recent activity" in result


def test_get_recent_activity_with_traces(client):
    trace = {
        "source": "agent",
        "intent": "test activity",
        "steps": [],
        "context": {"agent_id": "test", "domain": "test"},
    }
    client.ingest_trace(trace)
    result = get_recent_activity(client)
    assert isinstance(result, str)
    assert "test activity" in result
