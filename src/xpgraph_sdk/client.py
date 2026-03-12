"""XPGraph SDK client -- works locally or via HTTP."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class XPGClient:
    """Client for interacting with the Experience Graph.

    Works in two modes:
    - **Remote mode**: When base_url is provided, uses HTTP to call the REST API.
    - **Local mode**: When no base_url, uses local stores directly via StoreRegistry.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._http: Any = None  # lazy httpx.Client
        self._registry: Any = None  # lazy StoreRegistry

    def _get_http(self) -> Any:
        """Get or create an httpx client."""
        if self._http is None:
            import httpx  # noqa: PLC0415

            self._http = httpx.Client(base_url=self._base_url, timeout=30.0)
        return self._http

    def _get_registry(self) -> Any:
        """Get or create a local StoreRegistry."""
        if self._registry is None:
            from xpgraph.stores.registry import StoreRegistry  # noqa: PLC0415

            self._registry = StoreRegistry.from_config_dir()
        return self._registry

    @property
    def is_remote(self) -> bool:
        """Whether this client connects to a remote API."""
        return self._base_url is not None

    # -- Ingest --

    def ingest_trace(self, trace: dict[str, Any]) -> str:
        """Ingest a trace. Returns the trace_id."""
        if self.is_remote:
            resp = self._get_http().post("/api/v1/traces", json=trace)
            resp.raise_for_status()
            return resp.json()["trace_id"]

        from xpgraph.schemas.trace import Trace  # noqa: PLC0415

        t = Trace.model_validate(trace)
        registry = self._get_registry()
        return registry.trace_store.append(t)

    def ingest_evidence(self, evidence: dict[str, Any]) -> str:
        """Ingest evidence. Returns the evidence_id."""
        if self.is_remote:
            resp = self._get_http().post("/api/v1/evidence", json=evidence)
            resp.raise_for_status()
            return resp.json()["evidence_id"]

        from xpgraph.schemas.evidence import Evidence  # noqa: PLC0415

        e = Evidence.model_validate(evidence)
        registry = self._get_registry()
        registry.document_store.put(
            doc_id=e.evidence_id,
            content=e.content or "",
            metadata={
                "evidence_type": e.evidence_type,
                "source_origin": e.source_origin,
            },
        )
        return e.evidence_id

    # -- Retrieve --

    def search(
        self,
        query: str,
        *,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search documents. Returns list of result dicts."""
        if self.is_remote:
            params: dict[str, Any] = {"q": query, "limit": limit}
            if domain:
                params["domain"] = domain
            resp = self._get_http().get("/api/v1/search", params=params)
            resp.raise_for_status()
            return resp.json().get("results", [])

        registry = self._get_registry()
        filters: dict[str, Any] = {}
        if domain:
            filters["domain"] = domain
        return registry.document_store.search(query, limit=limit, filters=filters)

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Get a trace by ID."""
        if self.is_remote:
            resp = self._get_http().get(f"/api/v1/traces/{trace_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("trace")

        registry = self._get_registry()
        trace = registry.trace_store.get(trace_id)
        return trace.model_dump(mode="json") if trace else None

    def list_traces(
        self,
        *,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List recent traces."""
        if self.is_remote:
            params: dict[str, Any] = {"limit": limit}
            if domain:
                params["domain"] = domain
            resp = self._get_http().get("/api/v1/traces", params=params)
            resp.raise_for_status()
            return resp.json().get("traces", [])

        registry = self._get_registry()
        traces = registry.trace_store.query(domain=domain, limit=limit)
        return [
            {
                "trace_id": t.trace_id,
                "source": t.source.value,
                "intent": t.intent,
                "outcome": t.outcome.status.value if t.outcome else None,
                "domain": t.context.domain if t.context else None,
                "agent_id": t.context.agent_id if t.context else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in traces
        ]

    def assemble_pack(
        self,
        intent: str,
        *,
        domain: str | None = None,
        agent_id: str | None = None,
        max_items: int = 50,
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """Assemble a context pack. Returns pack dict."""
        if self.is_remote:
            resp = self._get_http().post(
                "/api/v1/packs",
                json={
                    "intent": intent,
                    "domain": domain,
                    "agent_id": agent_id,
                    "max_items": max_items,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()

        from xpgraph.retrieve.pack_builder import PackBuilder  # noqa: PLC0415
        from xpgraph.retrieve.strategies import (  # noqa: PLC0415
            GraphSearch,
            KeywordSearch,
        )
        from xpgraph.schemas.pack import PackBudget  # noqa: PLC0415

        registry = self._get_registry()
        builder = PackBuilder(
            strategies=[
                KeywordSearch(registry.document_store),
                GraphSearch(registry.graph_store),
            ]
        )
        budget = PackBudget(max_items=max_items, max_tokens=max_tokens)
        pack = builder.build(
            intent=intent, domain=domain, agent_id=agent_id, budget=budget
        )
        return {
            "pack_id": pack.pack_id,
            "intent": pack.intent,
            "domain": pack.domain,
            "agent_id": pack.agent_id,
            "count": len(pack.items),
            "items": [item.model_dump() for item in pack.items],
        }

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Get an entity by ID."""
        if self.is_remote:
            resp = self._get_http().get(f"/api/v1/entities/{entity_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("entity")

        registry = self._get_registry()
        return registry.graph_store.get_node(entity_id)

    # -- Curate --

    def create_entity(
        self,
        name: str,
        entity_type: str = "concept",
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Create an entity. Returns the node_id."""
        if self.is_remote:
            resp = self._get_http().post(
                "/api/v1/entities",
                json={
                    "entity_type": entity_type,
                    "name": name,
                    "properties": properties or {},
                },
            )
            resp.raise_for_status()
            return resp.json()["node_id"]

        registry = self._get_registry()
        props = dict(properties or {})
        props["name"] = name
        return registry.graph_store.upsert_node(
            node_id=None, node_type=entity_type, properties=props
        )

    def create_link(
        self,
        source_id: str,
        target_id: str,
        edge_kind: str = "entity_related_to",
    ) -> str:
        """Create a link between entities. Returns the edge_id."""
        if self.is_remote:
            resp = self._get_http().post(
                "/api/v1/links",
                json={
                    "source_id": source_id,
                    "target_id": target_id,
                    "edge_kind": edge_kind,
                },
            )
            resp.raise_for_status()
            return resp.json()["edge_id"]

        registry = self._get_registry()
        return registry.graph_store.upsert_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_kind,
        )

    # -- Lifecycle --

    def close(self) -> None:
        """Close any open connections."""
        if self._http is not None:
            self._http.close()
            self._http = None
        if self._registry is not None:
            self._registry.close()
            self._registry = None
