"""Base class for ingestion workers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog

from xpgraph.stores.registry import StoreRegistry

logger = structlog.get_logger(__name__)


class IngestionWorker(ABC):
    """Base for all ingestion workers.

    Implements a discover -> extract -> load pipeline that reads from an
    external source and populates the knowledge graph.
    """

    def __init__(self, registry: StoreRegistry) -> None:
        self._registry = registry

    @abstractmethod
    def discover(self, source_path: Path) -> list[dict[str, Any]]:
        """Discover entities and relationships from source."""

    @abstractmethod
    def extract(
        self, discovered: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract nodes and edges from discovered items.

        Returns:
            A ``(nodes, edges)`` tuple.
        """

    def load(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Load extracted nodes and edges into the graph store.

        Returns:
            A dict with ``nodes`` and ``edges`` counts.
        """
        graph = self._registry.graph_store
        node_count = 0
        for node in nodes:
            graph.upsert_node(
                node_id=node["node_id"],
                node_type=node["node_type"],
                properties=node.get("properties", {}),
            )
            node_count += 1

        edge_count = 0
        for edge in edges:
            graph.upsert_edge(
                source_id=edge["source_id"],
                target_id=edge["target_id"],
                edge_type=edge["edge_type"],
                properties=edge.get("properties"),
            )
            edge_count += 1

        logger.info(
            "ingestion_loaded",
            nodes=node_count,
            edges=edge_count,
            worker=type(self).__name__,
        )
        return {"nodes": node_count, "edges": edge_count}

    def run(self, source_path: Path) -> dict[str, int]:
        """Full pipeline: discover -> extract -> load."""
        logger.info(
            "ingestion_started",
            source=str(source_path),
            worker=type(self).__name__,
        )
        discovered = self.discover(source_path)
        nodes, edges = self.extract(discovered)
        counts = self.load(nodes, edges)
        logger.info(
            "ingestion_completed",
            source=str(source_path),
            worker=type(self).__name__,
            **counts,
        )
        return counts
