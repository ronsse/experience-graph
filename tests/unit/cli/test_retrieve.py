"""Tests for retrieve CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from xpgraph_cli.main import app

runner = CliRunner()


class TestRetrievePack:
    def test_pack_request(self) -> None:
        result = runner.invoke(
            app, ["retrieve", "pack", "--intent", "deploy checklist"],
        )
        assert result.exit_code == 0

    def test_pack_json(self) -> None:
        result = runner.invoke(app, [
            "retrieve", "pack",
            "--intent", "deploy",
            "--domain", "platform",
            "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["intent"] == "deploy"
        assert data["domain"] == "platform"


class TestRetrieveSearch:
    def test_search(self) -> None:
        result = runner.invoke(app, ["retrieve", "search", "kubernetes"])
        assert result.exit_code == 0

    def test_search_json(self) -> None:
        result = runner.invoke(app, [
            "retrieve", "search", "kubernetes",
            "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["query"] == "kubernetes"


class TestRetrieveTrace:
    def test_trace(self) -> None:
        result = runner.invoke(app, ["retrieve", "trace", "trace_123"])
        assert result.exit_code == 0

    def test_trace_json(self) -> None:
        result = runner.invoke(app, [
            "retrieve", "trace", "trace_123", "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["trace_id"] == "trace_123"


class TestRetrieveEntity:
    def test_entity(self) -> None:
        result = runner.invoke(app, ["retrieve", "entity", "ent_456"])
        assert result.exit_code == 0


class TestRetrievePrecedents:
    def test_precedents(self) -> None:
        result = runner.invoke(app, ["retrieve", "precedents"])
        assert result.exit_code == 0

    def test_precedents_with_domain(self) -> None:
        result = runner.invoke(app, [
            "retrieve", "precedents",
            "--domain", "platform",
            "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["domain"] == "platform"


class TestRetrieveHelp:
    def test_help(self) -> None:
        result = runner.invoke(app, ["retrieve", "--help"])
        assert result.exit_code == 0
        for cmd in ["pack", "search", "trace", "entity", "precedents"]:
            assert cmd in result.stdout
