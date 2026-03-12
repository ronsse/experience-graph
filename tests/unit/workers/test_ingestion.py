"""Tests for automated knowledge ingestion workers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xpgraph.stores.registry import StoreRegistry
from xpgraph_workers.ingestion.dbt import DbtManifestWorker
from xpgraph_workers.ingestion.openlineage import OpenLineageWorker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DBT_MANIFEST: dict = {
    "nodes": {
        "model.my_project.stg_orders": {
            "unique_id": "model.my_project.stg_orders",
            "resource_type": "model",
            "name": "stg_orders",
            "schema": "staging",
            "database": "analytics",
            "description": "Staged orders from source",
            "depends_on": {"nodes": ["source.my_project.raw.orders"]},
            "config": {"materialized": "view"},
            "tags": ["staging"],
        },
        "model.my_project.fct_orders": {
            "unique_id": "model.my_project.fct_orders",
            "resource_type": "model",
            "name": "fct_orders",
            "schema": "marts",
            "description": "Fact table for orders",
            "depends_on": {"nodes": ["model.my_project.stg_orders"]},
            "config": {"materialized": "table"},
            "tags": ["marts"],
        },
        "test.my_project.not_null_stg_orders_id": {
            "unique_id": "test.my_project.not_null_stg_orders_id",
            "resource_type": "test",
            "name": "not_null_stg_orders_id",
            "depends_on": {"nodes": ["model.my_project.stg_orders"]},
            "tags": [],
        },
    },
    "sources": {
        "source.my_project.raw.orders": {
            "unique_id": "source.my_project.raw.orders",
            "resource_type": "source",
            "name": "orders",
            "source_name": "raw",
            "schema": "public",
            "description": "Raw orders table",
        },
    },
}


SAMPLE_OL_EVENTS: list[dict] = [
    {
        "eventType": "COMPLETE",
        "job": {"namespace": "spark", "name": "etl_job"},
        "inputs": [{"namespace": "warehouse", "name": "raw.events"}],
        "outputs": [{"namespace": "warehouse", "name": "analytics.daily_events"}],
    },
    {
        "eventType": "COMPLETE",
        "job": {"namespace": "spark", "name": "agg_job"},
        "inputs": [{"namespace": "warehouse", "name": "analytics.daily_events"}],
        "outputs": [{"namespace": "warehouse", "name": "analytics.weekly_summary"}],
    },
]


@pytest.fixture
def registry(tmp_path: Path) -> StoreRegistry:
    """Create a real SQLite-backed registry in a temp directory."""
    stores_dir = tmp_path / "stores"
    stores_dir.mkdir()
    return StoreRegistry(stores_dir=stores_dir)


@pytest.fixture
def dbt_manifest_file(tmp_path: Path) -> Path:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(SAMPLE_DBT_MANIFEST))
    return p


@pytest.fixture
def ol_events_file(tmp_path: Path) -> Path:
    p = tmp_path / "events.json"
    p.write_text(json.dumps(SAMPLE_OL_EVENTS))
    return p


@pytest.fixture
def ol_events_ndjson_file(tmp_path: Path) -> Path:
    p = tmp_path / "events.ndjson"
    p.write_text("\n".join(json.dumps(e) for e in SAMPLE_OL_EVENTS))
    return p


# ---------------------------------------------------------------------------
# DbtManifestWorker — discover
# ---------------------------------------------------------------------------


class TestDbtDiscover:
    def test_discover_returns_all_resources(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        worker = DbtManifestWorker(registry)
        items = worker.discover(dbt_manifest_file)
        # 3 nodes + 1 source = 4
        assert len(items) == 4

    def test_discover_from_directory(
        self, registry: StoreRegistry, tmp_path: Path
    ) -> None:
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text(json.dumps(SAMPLE_DBT_MANIFEST))

        worker = DbtManifestWorker(registry)
        items = worker.discover(tmp_path)
        assert len(items) == 4


# ---------------------------------------------------------------------------
# DbtManifestWorker — extract
# ---------------------------------------------------------------------------


class TestDbtExtract:
    def test_extract_produces_correct_nodes(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        worker = DbtManifestWorker(registry)
        items = worker.discover(dbt_manifest_file)
        nodes, _edges = worker.extract(items)

        node_ids = {n["node_id"] for n in nodes}
        assert "model.my_project.stg_orders" in node_ids
        assert "source.my_project.raw.orders" in node_ids
        assert "test.my_project.not_null_stg_orders_id" in node_ids

        # Check node types
        type_map = {n["node_id"]: n["node_type"] for n in nodes}
        assert type_map["model.my_project.stg_orders"] == "dbt_model"
        assert type_map["source.my_project.raw.orders"] == "dbt_source"
        assert type_map["test.my_project.not_null_stg_orders_id"] == "dbt_test"

    def test_extract_model_properties(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        worker = DbtManifestWorker(registry)
        items = worker.discover(dbt_manifest_file)
        nodes, _edges = worker.extract(items)

        stg = next(n for n in nodes if n["node_id"] == "model.my_project.stg_orders")
        props = stg["properties"]
        assert props["name"] == "stg_orders"
        assert props["schema"] == "staging"
        assert props["materialized"] == "view"
        assert props["description"] == "Staged orders from source"

    def test_extract_source_properties(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        worker = DbtManifestWorker(registry)
        items = worker.discover(dbt_manifest_file)
        nodes, _edges = worker.extract(items)

        src = next(
            n for n in nodes if n["node_id"] == "source.my_project.raw.orders"
        )
        assert src["properties"]["source_name"] == "raw"

    def test_extract_produces_dependency_edges(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        worker = DbtManifestWorker(registry)
        items = worker.discover(dbt_manifest_file)
        _nodes, edges = worker.extract(items)

        # stg_orders depends on source
        assert any(
            e["source_id"] == "model.my_project.stg_orders"
            and e["target_id"] == "source.my_project.raw.orders"
            and e["edge_type"] == "depends_on"
            for e in edges
        )

        # fct_orders depends on stg_orders
        assert any(
            e["source_id"] == "model.my_project.fct_orders"
            and e["target_id"] == "model.my_project.stg_orders"
            and e["edge_type"] == "depends_on"
            for e in edges
        )


# ---------------------------------------------------------------------------
# OpenLineageWorker — discover
# ---------------------------------------------------------------------------


class TestOpenLineageDiscover:
    def test_discover_json_array(
        self, registry: StoreRegistry, ol_events_file: Path
    ) -> None:
        worker = OpenLineageWorker(registry)
        events = worker.discover(ol_events_file)
        assert len(events) == 2

    def test_discover_ndjson(
        self, registry: StoreRegistry, ol_events_ndjson_file: Path
    ) -> None:
        worker = OpenLineageWorker(registry)
        events = worker.discover(ol_events_ndjson_file)
        assert len(events) == 2


# ---------------------------------------------------------------------------
# OpenLineageWorker — extract
# ---------------------------------------------------------------------------


class TestOpenLineageExtract:
    def test_extract_produces_correct_nodes(
        self, registry: StoreRegistry, ol_events_file: Path
    ) -> None:
        worker = OpenLineageWorker(registry)
        events = worker.discover(ol_events_file)
        nodes, _edges = worker.extract(events)

        node_ids = {n["node_id"] for n in nodes}
        assert "job:spark:etl_job" in node_ids
        assert "job:spark:agg_job" in node_ids
        assert "dataset:warehouse:raw.events" in node_ids
        assert "dataset:warehouse:analytics.daily_events" in node_ids
        assert "dataset:warehouse:analytics.weekly_summary" in node_ids

    def test_extract_node_types(
        self, registry: StoreRegistry, ol_events_file: Path
    ) -> None:
        worker = OpenLineageWorker(registry)
        events = worker.discover(ol_events_file)
        nodes, _edges = worker.extract(events)

        type_map = {n["node_id"]: n["node_type"] for n in nodes}
        assert type_map["job:spark:etl_job"] == "job"
        assert type_map["dataset:warehouse:raw.events"] == "dataset"

    def test_extract_produces_correct_edges(
        self, registry: StoreRegistry, ol_events_file: Path
    ) -> None:
        worker = OpenLineageWorker(registry)
        events = worker.discover(ol_events_file)
        _nodes, edges = worker.extract(events)

        # etl_job reads raw.events
        assert any(
            e["source_id"] == "job:spark:etl_job"
            and e["target_id"] == "dataset:warehouse:raw.events"
            and e["edge_type"] == "reads_from"
            for e in edges
        )

        # etl_job writes daily_events
        assert any(
            e["source_id"] == "job:spark:etl_job"
            and e["target_id"] == "dataset:warehouse:analytics.daily_events"
            and e["edge_type"] == "writes_to"
            for e in edges
        )

    def test_extract_deduplicates_edges(
        self, registry: StoreRegistry
    ) -> None:
        """Duplicate events should not produce duplicate edges."""
        worker = OpenLineageWorker(registry)
        duplicate_events = [SAMPLE_OL_EVENTS[0], SAMPLE_OL_EVENTS[0]]
        _nodes, edges = worker.extract(duplicate_events)
        reads = [e for e in edges if e["edge_type"] == "reads_from"]
        writes = [e for e in edges if e["edge_type"] == "writes_to"]
        assert len(reads) == 1
        assert len(writes) == 1


# ---------------------------------------------------------------------------
# Full pipeline — load with real SQLite stores
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_dbt_full_pipeline(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        worker = DbtManifestWorker(registry)
        counts = worker.run(dbt_manifest_file)

        assert counts["nodes"] == 4
        assert counts["edges"] == 3
        assert counts["documents"] > 0

        # Verify nodes in graph store
        graph = registry.graph_store
        node = graph.get_node("model.my_project.stg_orders")
        assert node is not None
        assert node["node_type"] == "dbt_model"

        # Verify edges
        edges = graph.get_edges(
            "model.my_project.stg_orders", direction="outgoing", edge_type="depends_on"
        )
        assert len(edges) == 1
        assert edges[0]["target_id"] == "source.my_project.raw.orders"

    def test_openlineage_full_pipeline(
        self, registry: StoreRegistry, ol_events_file: Path
    ) -> None:
        worker = OpenLineageWorker(registry)
        counts = worker.run(ol_events_file)

        assert counts["nodes"] == 5  # 2 jobs + 3 datasets
        assert counts["edges"] == 4  # 2 reads + 2 writes

        graph = registry.graph_store
        node = graph.get_node("job:spark:etl_job")
        assert node is not None
        assert node["node_type"] == "job"

    def test_dbt_idempotency(
        self, registry: StoreRegistry, dbt_manifest_file: Path
    ) -> None:
        """Running twice should produce the same graph state."""
        worker = DbtManifestWorker(registry)
        counts1 = worker.run(dbt_manifest_file)
        counts2 = worker.run(dbt_manifest_file)

        assert counts1["nodes"] == counts2["nodes"]
        assert counts1["edges"] == counts2["edges"]

        graph = registry.graph_store
        assert graph.count_nodes() == 4
        assert graph.count_edges() == 3

    def test_openlineage_idempotency(
        self, registry: StoreRegistry, ol_events_file: Path
    ) -> None:
        """Running twice should produce the same graph state."""
        worker = OpenLineageWorker(registry)
        worker.run(ol_events_file)
        worker.run(ol_events_file)

        graph = registry.graph_store
        assert graph.count_nodes() == 5
        assert graph.count_edges() == 4
