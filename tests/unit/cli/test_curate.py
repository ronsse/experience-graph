"""Tests for curate CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from xpgraph_cli.main import app

runner = CliRunner()


class TestCuratePromote:
    def test_promote(self) -> None:
        result = runner.invoke(app, [
            "curate", "promote", "trace_123",
            "--title", "Always check locks",
            "--description", "Learned from incident",
        ])
        assert result.exit_code == 0
        assert "Command prepared" in result.stdout or "prepared" in result.stdout

    def test_promote_json(self) -> None:
        result = runner.invoke(app, [
            "curate", "promote", "trace_123",
            "--title", "T", "--description", "D",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout.strip())
        assert data["operation"] == "precedent.promote"
        assert data["args"]["trace_id"] == "trace_123"


class TestCurateLink:
    def test_link(self) -> None:
        result = runner.invoke(app, ["curate", "link", "ent_1", "ent_2"])
        assert result.exit_code == 0

    def test_link_with_kind(self) -> None:
        result = runner.invoke(app, [
            "curate", "link", "ent_1", "ent_2",
            "--kind", "entity_depends_on",
            "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["args"]["edge_kind"] == "entity_depends_on"


class TestCurateLabel:
    def test_label(self) -> None:
        result = runner.invoke(app, ["curate", "label", "ent_1", "important"])
        assert result.exit_code == 0

    def test_label_json(self) -> None:
        result = runner.invoke(app, [
            "curate", "label", "ent_1", "critical",
            "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["args"]["label"] == "critical"


class TestCurateFeedback:
    def test_feedback(self) -> None:
        result = runner.invoke(app, ["curate", "feedback", "trace_1", "0.9"])
        assert result.exit_code == 0

    def test_feedback_with_comment(self) -> None:
        result = runner.invoke(app, [
            "curate", "feedback", "trace_1", "0.8",
            "--comment", "Good approach",
            "--format", "json",
        ])
        data = json.loads(result.stdout.strip())
        assert data["args"]["rating"] == 0.8
        assert data["args"]["comment"] == "Good approach"


class TestCurateHelp:
    def test_help(self) -> None:
        result = runner.invoke(app, ["curate", "--help"])
        assert result.exit_code == 0
        for cmd in ["promote", "link", "label", "feedback"]:
            assert cmd in result.stdout
