"""OpenLineage event ingestion worker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from xpgraph.stores.registry import StoreRegistry
from xpgraph_workers.ingestion.base import IngestionWorker

logger = structlog.get_logger(__name__)


def _dataset_id(namespace: str, name: str) -> str:
    """Build a stable node ID for a dataset."""
    return f"dataset:{namespace}:{name}"


def _job_id(namespace: str, name: str) -> str:
    """Build a stable node ID for a job."""
    return f"job:{namespace}:{name}"


def _ensure_dataset(
    dataset: dict[str, Any],
    seen_nodes: dict[str, dict[str, Any]],
) -> str | None:
    """Register a dataset node if not already seen.

    Returns the dataset node ID, or ``None`` if the dataset is invalid.
    """
    ds_ns = dataset.get("namespace", "")
    ds_name = dataset.get("name", "")
    if not ds_ns or not ds_name:
        return None
    did = _dataset_id(ds_ns, ds_name)
    if did not in seen_nodes:
        props: dict[str, Any] = {
            "namespace": ds_ns,
            "name": ds_name,
        }
        facets = dataset.get("facets") or {}
        if facets:
            props["facets"] = facets
        seen_nodes[did] = {
            "node_id": did,
            "node_type": "dataset",
            "properties": props,
        }
    return did


class OpenLineageWorker(IngestionWorker):
    """Ingest OpenLineage events into the knowledge graph.

    Creates graph nodes for datasets and jobs, and edges for
    ``reads_from`` and ``writes_to`` relationships.
    """

    def __init__(self, registry: StoreRegistry) -> None:
        super().__init__(registry)

    def discover(self, source_path: Path) -> list[dict[str, Any]]:
        """Read OpenLineage events from a JSON file.

        Supports both a JSON array of events and newline-delimited JSON
        (one event per line).
        """
        raw = source_path.read_text().strip()
        events: list[dict[str, Any]] = []

        if raw.startswith("["):
            events = json.loads(raw)
        else:
            for raw_line in raw.splitlines():
                stripped = raw_line.strip()
                if stripped:
                    events.append(json.loads(stripped))

        logger.info(
            "openlineage_discover_complete",
            events=len(events),
            path=str(source_path),
        )
        return events

    def extract(
        self, discovered: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Convert OpenLineage events into graph nodes and edges."""
        seen_nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        for event in discovered:
            job_info = event.get("job", {})
            job_ns = job_info.get("namespace", "")
            job_name = job_info.get("name", "")
            if not job_ns or not job_name:
                continue

            jid = _job_id(job_ns, job_name)
            if jid not in seen_nodes:
                seen_nodes[jid] = {
                    "node_id": jid,
                    "node_type": "job",
                    "properties": {
                        "namespace": job_ns,
                        "name": job_name,
                    },
                }

            for inp in event.get("inputs", []):
                did = _ensure_dataset(inp, seen_nodes)
                if did:
                    edges.append({
                        "source_id": jid,
                        "target_id": did,
                        "edge_type": "reads_from",
                    })

            for out in event.get("outputs", []):
                did = _ensure_dataset(out, seen_nodes)
                if did:
                    edges.append({
                        "source_id": jid,
                        "target_id": did,
                        "edge_type": "writes_to",
                    })

        # Deduplicate edges
        unique_edges: list[dict[str, Any]] = []
        seen_edge_keys: set[tuple[str, str, str]] = set()
        for edge in edges:
            key = (
                edge["source_id"],
                edge["target_id"],
                edge["edge_type"],
            )
            if key not in seen_edge_keys:
                seen_edge_keys.add(key)
                unique_edges.append(edge)

        nodes = list(seen_nodes.values())
        logger.info(
            "openlineage_extract_complete",
            nodes=len(nodes),
            edges=len(unique_edges),
        )
        return nodes, unique_edges
