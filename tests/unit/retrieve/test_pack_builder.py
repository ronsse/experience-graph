"""Tests for PackBuilder."""

from __future__ import annotations

from unittest.mock import MagicMock

from xpgraph.retrieve.pack_builder import PackBuilder
from xpgraph.retrieve.strategies import SearchStrategy
from xpgraph.schemas.pack import PackBudget, PackItem


def _make_strategy(name: str, items: list[PackItem]) -> SearchStrategy:
    """Create a mock strategy returning given items."""
    strategy = MagicMock(spec=SearchStrategy)
    strategy.name = name
    strategy.search.return_value = items
    return strategy


def _item(item_id: str, score: float, excerpt: str = "text") -> PackItem:
    return PackItem(
        item_id=item_id, item_type="document", excerpt=excerpt, relevance_score=score
    )


class TestPackBuilder:
    def test_build_with_no_strategies(self) -> None:
        builder = PackBuilder()
        pack = builder.build("test query")
        assert pack.intent == "test query"
        assert pack.items == []
        assert pack.retrieval_report.queries_run == 0

    def test_build_with_single_strategy(self) -> None:
        s = _make_strategy("keyword", [_item("d1", 0.9), _item("d2", 0.7)])
        builder = PackBuilder(strategies=[s])
        pack = builder.build("search")
        assert len(pack.items) == 2
        assert pack.items[0].item_id == "d1"
        assert pack.retrieval_report.queries_run == 1
        assert "keyword" in pack.retrieval_report.strategies_used

    def test_build_with_multiple_strategies(self) -> None:
        s1 = _make_strategy("keyword", [_item("d1", 0.9)])
        s2 = _make_strategy("semantic", [_item("v1", 0.85)])
        builder = PackBuilder(strategies=[s1, s2])
        pack = builder.build("search")
        assert len(pack.items) == 2
        assert pack.retrieval_report.queries_run == 2

    def test_deduplication_keeps_highest_score(self) -> None:
        s1 = _make_strategy("keyword", [_item("d1", 0.7)])
        s2 = _make_strategy("semantic", [_item("d1", 0.9)])
        builder = PackBuilder(strategies=[s1, s2])
        pack = builder.build("search")
        assert len(pack.items) == 1
        assert pack.items[0].relevance_score == 0.9

    def test_sorted_by_relevance(self) -> None:
        s = _make_strategy(
            "kw", [_item("a", 0.3), _item("b", 0.9), _item("c", 0.6)]
        )
        builder = PackBuilder(strategies=[s])
        pack = builder.build("q")
        scores = [item.relevance_score for item in pack.items]
        assert scores == sorted(scores, reverse=True)

    def test_budget_max_items(self) -> None:
        items = [_item(f"d{i}", 1.0 - i * 0.1) for i in range(10)]
        s = _make_strategy("kw", items)
        builder = PackBuilder(strategies=[s])
        pack = builder.build("q", budget=PackBudget(max_items=3, max_tokens=100000))
        assert len(pack.items) == 3

    def test_budget_max_tokens(self) -> None:
        # Each item has 100 chars => ~26 tokens (100//4+1)
        items = [
            _item(f"d{i}", 1.0 - i * 0.01, excerpt="x" * 100) for i in range(20)
        ]
        s = _make_strategy("kw", items)
        builder = PackBuilder(strategies=[s])
        # Budget of 100 tokens, each item ~26 tokens, so ~3-4 items fit
        pack = builder.build("q", budget=PackBudget(max_items=50, max_tokens=100))
        assert len(pack.items) < 20

    def test_domain_and_agent_id(self) -> None:
        builder = PackBuilder()
        pack = builder.build("q", domain="platform", agent_id="agent-1")
        assert pack.domain == "platform"
        assert pack.agent_id == "agent-1"

    def test_retrieval_report(self) -> None:
        s1 = _make_strategy("kw", [_item("d1", 0.9), _item("d2", 0.8)])
        s2 = _make_strategy("sem", [_item("v1", 0.7)])
        builder = PackBuilder(strategies=[s1, s2])
        pack = builder.build("q")
        assert pack.retrieval_report.candidates_found == 3
        assert pack.retrieval_report.items_selected == 3
        assert pack.retrieval_report.strategies_used == ["kw", "sem"]

    def test_add_strategy(self) -> None:
        builder = PackBuilder()
        s = _make_strategy("kw", [_item("d1", 0.5)])
        builder.add_strategy(s)
        pack = builder.build("q")
        assert len(pack.items) == 1

    def test_strategy_failure_continues(self) -> None:
        good = _make_strategy("kw", [_item("d1", 0.9)])
        bad = _make_strategy("bad", [])
        bad.search.side_effect = RuntimeError("oops")
        builder = PackBuilder(strategies=[bad, good])
        pack = builder.build("q")
        assert len(pack.items) == 1  # good strategy still works

    def test_filters_passed_to_strategies(self) -> None:
        s = _make_strategy("kw", [])
        builder = PackBuilder(strategies=[s])
        builder.build("q", filters={"domain": "platform"})
        call_kwargs = s.search.call_args
        assert call_kwargs[1]["filters"] == {"domain": "platform"}

    def test_pack_has_assembled_at(self) -> None:
        builder = PackBuilder()
        pack = builder.build("q")
        assert pack.assembled_at is not None

    def test_budget_preserved_in_pack(self) -> None:
        budget = PackBudget(max_items=5, max_tokens=1000)
        builder = PackBuilder()
        pack = builder.build("q", budget=budget)
        assert pack.budget.max_items == 5
        assert pack.budget.max_tokens == 1000
