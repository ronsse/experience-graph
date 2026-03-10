"""Search strategies for pack assembly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from xpgraph.schemas.pack import PackItem

logger = structlog.get_logger()


class SearchStrategy(ABC):
    """Base class for retrieval strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for reporting."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[PackItem]:
        """Execute search and return ranked PackItems."""


def _apply_importance(base_score: float, metadata: dict[str, Any]) -> float:
    """Apply importance weighting: base_score * (1.0 + importance)."""
    importance = float(metadata.get("auto_importance", 0.0))
    importance = max(0.0, min(1.0, importance))  # clamp 0-1
    return base_score * (1.0 + importance)


class KeywordSearch(SearchStrategy):
    """Full-text keyword search via DocumentStore."""

    def __init__(self, document_store: Any) -> None:
        self._store = document_store

    @property
    def name(self) -> str:
        return "keyword"

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[PackItem]:
        results = self._store.search(query, limit=limit, filters=filters)
        items = []
        for doc in results:
            metadata = doc.get("metadata", {})
            base_score = abs(doc.get("rank", 0.0))
            score = _apply_importance(base_score, metadata)
            items.append(
                PackItem(
                    item_id=doc["doc_id"],
                    item_type="document",
                    excerpt=doc.get("content", "")[:500],
                    relevance_score=score,
                    metadata={"source_strategy": "keyword", **metadata},
                )
            )
        return sorted(items, key=lambda x: x.relevance_score, reverse=True)


class SemanticSearch(SearchStrategy):
    """Vector similarity search via VectorStore."""

    def __init__(self, vector_store: Any, embedding_fn: Any = None) -> None:
        self._store = vector_store
        self._embedding_fn = embedding_fn  # callable(str) -> list[float]

    @property
    def name(self) -> str:
        return "semantic"

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[PackItem]:
        if self._embedding_fn is None:
            logger.warning("semantic_search_no_embedding_fn")
            return []

        query_vector = self._embedding_fn(query)
        results = self._store.query(query_vector, top_k=limit, filters=filters)
        items = []
        for result in results:
            metadata = result.get("metadata", {})
            base_score = result.get("score", 0.0)
            score = _apply_importance(base_score, metadata)
            items.append(
                PackItem(
                    item_id=result["item_id"],
                    item_type="vector",
                    excerpt=metadata.get("content", metadata.get("excerpt", ""))[:500],
                    relevance_score=score,
                    metadata={"source_strategy": "semantic", **metadata},
                )
            )
        return sorted(items, key=lambda x: x.relevance_score, reverse=True)


class GraphSearch(SearchStrategy):
    """Graph traversal search via GraphStore."""

    def __init__(self, graph_store: Any) -> None:
        self._store = graph_store

    @property
    def name(self) -> str:
        return "graph"

    def search(
        self,
        query: str,  # noqa: ARG002
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[PackItem]:
        seed_ids: list[str] = []
        if filters and "seed_ids" in filters:
            seed_ids = filters.pop("seed_ids")

        if seed_ids:
            depth = filters.pop("depth", 2) if filters else 2
            subgraph = self._store.get_subgraph(seed_ids, depth=depth)
            nodes = subgraph.get("nodes", [])
        else:
            node_type = filters.pop("node_type", None) if filters else None
            nodes = self._store.query(
                node_type=node_type, properties=filters, limit=limit,
            )

        items = []
        for i, node in enumerate(nodes[:limit]):
            props = node.get("properties", {})
            base_score = max(0.0, 1.0 - (i * 0.05))
            score = _apply_importance(base_score, props)
            excerpt = props.get(
                "description", props.get("name", props.get("title", "")),
            )
            items.append(
                PackItem(
                    item_id=node["node_id"],
                    item_type="entity",
                    excerpt=str(excerpt)[:500],
                    relevance_score=score,
                    metadata={
                        "source_strategy": "graph",
                        "node_type": node.get("node_type", ""),
                        **props,
                    },
                )
            )
        return sorted(items, key=lambda x: x.relevance_score, reverse=True)
