"""Tests for Pack schema."""

from __future__ import annotations

from xpgraph.schemas import Pack, PackBudget, PackItem, RetrievalReport


class TestPack:
    """Tests for Pack model."""

    def test_pack_with_items(self) -> None:
        items = [
            PackItem(
                item_id="tr_1", item_type="trace",
                excerpt="did X", relevance_score=0.95,
            ),
            PackItem(item_id="ev_1", item_type="evidence", excerpt="doc Y"),
        ]
        p = Pack(intent="debug auth failure", items=items)
        assert len(p.pack_id) == 26
        assert p.intent == "debug auth failure"
        assert len(p.items) == 2
        assert p.items[0].relevance_score == 0.95

    def test_pack_with_budget(self) -> None:
        budget = PackBudget(max_items=10, max_tokens=4000)
        p = Pack(intent="summarize sprint", budget=budget)
        assert p.budget.max_items == 10
        assert p.budget.max_tokens == 4000

    def test_pack_with_retrieval_report(self) -> None:
        report = RetrievalReport(
            queries_run=3,
            candidates_found=42,
            items_selected=8,
            duration_ms=150,
            strategies_used=["semantic", "keyword"],
        )
        p = Pack(
            intent="find related precedents",
            retrieval_report=report,
            domain="infrastructure",
            agent_id="agent_007",
            policies_applied=["pol_1"],
        )
        assert p.retrieval_report.queries_run == 3
        assert p.retrieval_report.items_selected == 8
        assert p.domain == "infrastructure"
        assert p.policies_applied == ["pol_1"]

    def test_pack_default_budget(self) -> None:
        p = Pack(intent="test defaults")
        assert p.budget.max_items == 50
        assert p.budget.max_tokens == 8000
        assert p.retrieval_report.queries_run == 0
