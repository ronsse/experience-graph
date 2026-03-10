"""Tests for admin CLI commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from xpgraph_cli.main import app

runner = CliRunner()


class TestAdminInit:
    def test_init_creates_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        result = runner.invoke(app, ["admin", "init"])
        assert result.exit_code == 0
        assert (tmp_path / "config" / "config.yaml").exists()
        assert (tmp_path / "data" / "stores").exists()

    def test_init_custom_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        custom = str(tmp_path / "custom")
        result = runner.invoke(app, ["admin", "init", "--data-dir", custom])
        assert result.exit_code == 0
        assert (tmp_path / "custom" / "stores").exists()

    def test_init_no_overwrite_without_force(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        runner.invoke(app, ["admin", "init"])
        result = runner.invoke(app, ["admin", "init"])
        assert result.exit_code == 0
        assert "already exists" in result.stdout or "exists" in result.stdout

    def test_init_force_overwrites(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        runner.invoke(app, ["admin", "init"])
        result = runner.invoke(app, ["admin", "init", "--force"])
        assert result.exit_code == 0

    def test_init_json_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        result = runner.invoke(app, ["admin", "init", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout.strip())
        assert data["status"] == "initialized"


class TestAdminHealth:
    def test_health_uninitialized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        result = runner.invoke(app, ["admin", "health"])
        assert result.exit_code == 0

    def test_health_after_init(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        runner.invoke(app, ["admin", "init"])
        result = runner.invoke(app, ["admin", "health"])
        assert result.exit_code == 0

    def test_health_json_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XPG_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("XPG_DATA_DIR", str(tmp_path / "data"))
        runner.invoke(app, ["admin", "init"])
        result = runner.invoke(app, ["admin", "health", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout.strip())
        assert data["config"] is True
        assert data["data_dir"] is True


class TestAppStructure:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Experience Graph" in result.stdout

    def test_admin_help(self):
        result = runner.invoke(app, ["admin", "--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout
        assert "health" in result.stdout

    def test_command_groups_exist(self):
        result = runner.invoke(app, ["--help"])
        for group in ["admin", "ingest", "curate", "retrieve", "analyze", "worker"]:
            assert group in result.stdout
