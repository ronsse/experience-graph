"""dbt manifest ingestion worker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from xpgraph.stores.registry import StoreRegistry
from xpgraph_workers.ingestion.base import IngestionWorker

logger = structlog.get_logger(__name__)

_RESOURCE_TYPE_MAP: dict[str, str] = {
    "model": "dbt_model",
    "seed": "dbt_seed",
    "snapshot": "dbt_snapshot",
    "source": "dbt_source",
    "test": "dbt_test",
}


class DbtManifestWorker(IngestionWorker):
    """Ingest a dbt ``manifest.json`` into the knowledge graph.

    Creates graph nodes for models, seeds, snapshots, sources, and tests,
    and edges for ``depends_on`` relationships.  Descriptions are also
    indexed into the document store for full-text search.
    """

    def __init__(self, registry: StoreRegistry) -> None:
        super().__init__(registry)

    def discover(self, source_path: Path) -> list[dict[str, Any]]:
        """Read and parse a dbt manifest, returning raw resource dicts."""
        path = source_path
        if path.is_dir():
            path = path / "target" / "manifest.json"

        raw = path.read_text()
        manifest = json.loads(raw)

        items: list[dict[str, Any]] = list(manifest.get("nodes", {}).values())
        items.extend(manifest.get("sources", {}).values())

        logger.info("dbt_discover_complete", items=len(items), path=str(source_path))
        return items

    def extract(
        self, discovered: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Convert raw dbt resources into graph nodes and edges."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for resource in discovered:
            unique_id: str = resource["unique_id"]
            resource_type: str = resource.get("resource_type", "model")
            node_type = _RESOURCE_TYPE_MAP.get(resource_type, f"dbt_{resource_type}")

            properties: dict[str, Any] = {
                "name": resource.get("name", ""),
                "unique_id": unique_id,
            }

            # Optional fields -- only include when present
            for field in ("schema", "database", "description", "tags"):
                if resource.get(field):
                    properties[field] = resource[field]

            if resource_type == "model":
                config = resource.get("config", {})
                materialized = config.get("materialized")
                if materialized:
                    properties["materialized"] = materialized

            if resource_type == "source":
                source_name = resource.get("source_name")
                if source_name:
                    properties["source_name"] = source_name

            nodes.append(
                {
                    "node_id": unique_id,
                    "node_type": node_type,
                    "properties": properties,
                }
            )

            # Dependency edges
            depends_on = resource.get("depends_on", {})
            if isinstance(depends_on, dict):
                dep_nodes: list[str] = depends_on.get("nodes", [])
            else:
                dep_nodes = []
            edges.extend(
                {
                    "source_id": unique_id,
                    "target_id": dep_id,
                    "edge_type": "depends_on",
                }
                for dep_id in dep_nodes
            )

        logger.info(
            "dbt_extract_complete",
            nodes=len(nodes),
            edges=len(edges),
        )
        return nodes, edges

    def load(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Load nodes/edges and also index descriptions into the document store."""
        counts = super().load(nodes, edges)

        # Index descriptions
        doc_store = self._registry.document_store
        doc_count = 0
        for node in nodes:
            desc = node["properties"].get("description", "")
            if desc:
                doc_store.put(
                    doc_id=f"dbt:{node['node_id']}",
                    content=desc,
                    metadata={
                        "source": "dbt",
                        "node_type": node["node_type"],
                        "name": node["properties"].get("name", ""),
                        "unique_id": node["node_id"],
                    },
                )
                doc_count += 1

        counts["documents"] = doc_count
        logger.info("dbt_documents_indexed", documents=doc_count)
        return counts
