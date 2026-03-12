"""Pack builder — orchestrates search strategies to assemble retrieval packs."""

from __future__ import annotations

from typing import Any

import structlog

from xpgraph.core.base import utc_now
from xpgraph.retrieve.strategies import SearchStrategy
from xpgraph.schemas.pack import Pack, PackBudget, PackItem, RetrievalReport
from xpgraph.stores.base.event_log import EventLog, EventType

logger = structlog.get_logger()


class PackBuilder:
    """Assembles retrieval packs by running search strategies and applying budgets.

    Usage::

        builder = PackBuilder(strategies=[keyword, semantic, graph])
        pack = builder.build(intent="deploy checklist", domain="platform")
    """

    def __init__(
        self,
        strategies: list[SearchStrategy] | None = None,
        event_log: EventLog | None = None,
    ) -> None:
        self._strategies = strategies or []
        self._event_log = event_log

    def add_strategy(self, strategy: SearchStrategy) -> None:
        """Add a search strategy."""
        self._strategies.append(strategy)

    def build(
        self,
        intent: str,
        *,
        domain: str | None = None,
        agent_id: str | None = None,
        budget: PackBudget | None = None,
        filters: dict[str, Any] | None = None,
        limit_per_strategy: int = 20,
    ) -> Pack:
        """Assemble a pack by running all strategies and applying budget.

        Steps:
            1. Run each strategy with the intent as query.
            2. Collect all PackItems.
            3. Deduplicate by item_id (keep highest score).
            4. Sort by relevance_score descending.
            5. Apply budget limits (max_items, then max_tokens).
            6. Build RetrievalReport.
            7. Return Pack.
        """
        budget = budget or PackBudget()
        all_items: list[PackItem] = []
        strategies_used: list[str] = []
        candidates_found = 0

        for strategy in self._strategies:
            try:
                items = strategy.search(
                    intent,
                    limit=limit_per_strategy,
                    filters=dict(filters) if filters else None,
                )
                candidates_found += len(items)
                all_items.extend(items)
                strategies_used.append(strategy.name)
                logger.debug(
                    "strategy_completed", strategy=strategy.name, items=len(items)
                )
            except Exception:
                logger.exception("strategy_failed", strategy=strategy.name)
                continue

        # Deduplicate by item_id (keep highest relevance_score)
        deduped = self._deduplicate(all_items)

        # Sort by relevance_score descending
        deduped.sort(key=lambda x: x.relevance_score, reverse=True)

        # Apply budget: max_items first
        selected = deduped[: budget.max_items]

        # Apply budget: max_tokens (estimate ~4 chars per token)
        selected = self._apply_token_budget(selected, budget.max_tokens)

        report = RetrievalReport(
            queries_run=len(strategies_used),
            candidates_found=candidates_found,
            items_selected=len(selected),
            duration_ms=0,
            strategies_used=strategies_used,
        )

        pack = Pack(
            intent=intent,
            items=selected,
            retrieval_report=report,
            budget=budget,
            domain=domain,
            agent_id=agent_id,
            assembled_at=utc_now(),
        )

        # Emit telemetry event
        if self._event_log is not None:
            self._emit_telemetry(pack)

        return pack

    def _emit_telemetry(self, pack: Pack) -> None:
        """Emit a ContextRetrievalEvent for observability."""
        self._event_log.emit(  # type: ignore[union-attr]
            EventType.PACK_ASSEMBLED,
            source="pack_builder",
            entity_id=pack.pack_id,
            entity_type="pack",
            payload={
                "intent": pack.intent,
                "domain": pack.domain,
                "agent_id": pack.agent_id,
                "items_count": len(pack.items),
                "injected_item_ids": [item.item_id for item in pack.items],
                "strategies_used": pack.retrieval_report.strategies_used,
                "candidates_found": pack.retrieval_report.candidates_found,
                "budget_max_items": pack.budget.max_items,
                "budget_max_tokens": pack.budget.max_tokens,
            },
        )

    def _deduplicate(self, items: list[PackItem]) -> list[PackItem]:
        """Deduplicate by item_id, keeping the entry with highest relevance_score."""
        seen: dict[str, PackItem] = {}
        for item in items:
            existing = seen.get(item.item_id)
            if existing is None or item.relevance_score > existing.relevance_score:
                seen[item.item_id] = item
        return list(seen.values())

    def _apply_token_budget(
        self, items: list[PackItem], max_tokens: int
    ) -> list[PackItem]:
        """Trim items to fit within token budget (estimated at ~4 chars per token)."""
        result: list[PackItem] = []
        total_tokens = 0
        for item in items:
            item_tokens = len(item.excerpt) // 4 + 1
            if total_tokens + item_tokens > max_tokens:
                break
            result.append(item)
            total_tokens += item_tokens
        return result
