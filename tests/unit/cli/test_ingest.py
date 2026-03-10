"""Tests for ingest CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from xpgraph_cli.main import app

runner = CliRunner()


def _trace_json() -> str:
    return json.dumps({
        "source": "agent",
        "intent": "deploy service",
        "steps": [],
        "context": {"agent_id": "agent-1", "domain": "platform"},
    })


def _evidence_json() -> str:
    return json.dumps({
        "evidence_type": "snippet",
        "content": "SELECT * FROM users",
        "source_origin": "trace",
    })


class TestIngestTrace:
    def test_ingest_trace_from_file(self, tmp_path: object) -> None:
        f = tmp_path / "trace.json"  # type: ignore[operator]
        f.write_text(_trace_json())
        result = runner.invoke(app, ["ingest", "trace", str(f)])
        assert result.exit_code == 0
        assert "accepted" in result.stdout.lower() or "Trace accepted" in result.stdout

    def test_ingest_trace_json_format(self, tmp_path: object) -> None:
        f = tmp_path / "trace.json"  # type: ignore[operator]
        f.write_text(_trace_json())
        result = runner.invoke(app, ["ingest", "trace", str(f), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout.strip())
        assert data["status"] == "accepted"
        assert "trace_id" in data

    def test_ingest_trace_from_stdin(self) -> None:
        result = runner.invoke(app, ["ingest", "trace", "-"], input=_trace_json())
        assert result.exit_code == 0

    def test_ingest_trace_invalid_json(self, tmp_path: object) -> None:
        f = tmp_path / "bad.json"  # type: ignore[operator]
        f.write_text("not json")
        result = runner.invoke(app, ["ingest", "trace", str(f)])
        assert result.exit_code == 1

    def test_ingest_trace_invalid_schema(self, tmp_path: object) -> None:
        f = tmp_path / "bad.json"  # type: ignore[operator]
        f.write_text(json.dumps({"bogus": "data"}))
        result = runner.invoke(app, ["ingest", "trace", str(f)])
        assert result.exit_code == 1

    def test_ingest_trace_file_not_found(self) -> None:
        result = runner.invoke(app, ["ingest", "trace", "/nonexistent/file.json"])
        assert result.exit_code == 1


class TestIngestEvidence:
    def test_ingest_evidence_from_file(self, tmp_path: object) -> None:
        f = tmp_path / "evidence.json"  # type: ignore[operator]
        f.write_text(_evidence_json())
        result = runner.invoke(app, ["ingest", "evidence", str(f)])
        assert result.exit_code == 0
        assert "accepted" in result.stdout.lower()

    def test_ingest_evidence_json_format(self, tmp_path: object) -> None:
        f = tmp_path / "evidence.json"  # type: ignore[operator]
        f.write_text(_evidence_json())
        result = runner.invoke(app, ["ingest", "evidence", str(f), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout.strip())
        assert data["status"] == "accepted"

    def test_ingest_evidence_invalid(self, tmp_path: object) -> None:
        f = tmp_path / "bad.json"  # type: ignore[operator]
        f.write_text(json.dumps({"bad": "data"}))
        result = runner.invoke(app, ["ingest", "evidence", str(f)])
        assert result.exit_code == 1

    def test_ingest_evidence_file_not_found(self) -> None:
        result = runner.invoke(app, ["ingest", "evidence", "/nonexistent.json"])
        assert result.exit_code == 1


class TestIngestHelp:
    def test_ingest_help(self) -> None:
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "trace" in result.stdout
        assert "evidence" in result.stdout
