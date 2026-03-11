"""Tests for enrichment service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from xpgraph_workers.enrichment.service import (
    EnrichmentResult,
    EnrichmentService,
    normalize_tag,
)

# ---------------------------------------------------------------------------
# normalize_tag
# ---------------------------------------------------------------------------


class TestNormalizeTag:
    def test_spaces_to_hyphens(self):
        assert normalize_tag("hello world") == "hello-world"

    def test_underscores_to_hyphens(self):
        assert normalize_tag("hello_world") == "hello-world"

    def test_special_chars_removed(self):
        assert normalize_tag("hello!@#world") == "helloworld"

    def test_consecutive_hyphens_collapsed(self):
        assert normalize_tag("hello---world") == "hello-world"

    def test_leading_trailing_hyphens_stripped(self):
        assert normalize_tag("-hello-") == "hello"

    def test_mixed_case_lowered(self):
        assert normalize_tag("Hello World") == "hello-world"

    def test_slash_preserved(self):
        assert normalize_tag("lang/python") == "lang/python"

    def test_whitespace_stripped(self):
        assert normalize_tag("  spaced  ") == "spaced"


# ---------------------------------------------------------------------------
# EnrichmentResult model
# ---------------------------------------------------------------------------


class TestEnrichmentResult:
    def test_defaults(self):
        result = EnrichmentResult()
        assert result.auto_tags == []
        assert result.auto_class is None
        assert result.auto_summary is None
        assert result.auto_importance == 0.0
        assert result.success is True
        assert result.error is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValueError):
            EnrichmentResult(unexpected_field="boom")

    def test_explicit_values(self):
        result = EnrichmentResult(
            auto_tags=["python", "ai"],
            auto_class="research",
            auto_summary="A summary.",
            auto_importance=0.75,
            tag_confidence=0.9,
            class_confidence=0.85,
        )
        assert result.auto_tags == ["python", "ai"]
        assert result.auto_importance == 0.75


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

VALID_JSON = json.dumps(
    {
        "tags": ["python", "machine learning"],
        "class": "research",
        "summary": "A research paper on ML.",
        "importance": 0.7,
        "tag_confidence": 0.9,
        "class_confidence": 0.85,
    }
)


class TestParseResponse:
    @pytest.fixture
    def service(self):
        return EnrichmentService(llm=AsyncMock())

    def test_valid_json(self, service):
        result = service._parse_response(VALID_JSON)
        assert result.success is True
        assert result.auto_tags == ["python", "machine-learning"]
        assert result.auto_class == "research"
        assert result.auto_summary == "A research paper on ML."
        assert result.auto_importance == 0.7

    def test_json_in_code_fence(self, service):
        fenced = f"```json\n{VALID_JSON}\n```"
        result = service._parse_response(fenced)
        assert result.success is True
        assert result.auto_class == "research"

    def test_json_in_surrounding_text(self, service):
        text = f"Here is the result:\n{VALID_JSON}\nDone."
        result = service._parse_response(text)
        assert result.success is True
        assert result.auto_class == "research"

    def test_invalid_json_error(self, service):
        result = service._parse_response("not json at all")
        assert result.success is False
        assert result.error is not None
        assert "No JSON found" in result.error

    def test_invalid_classification_set_to_none(self, service):
        data = {
            "tags": ["python"],
            "class": "nonexistent-class",
            "summary": "A summary.",
            "importance": 0.5,
        }
        result = service._parse_response(json.dumps(data))
        assert result.auto_class is None

    def test_importance_clamped(self, service):
        data = {
            "tags": [],
            "class": "notes",
            "summary": "test",
            "importance": 5.0,
        }
        result = service._parse_response(json.dumps(data))
        assert result.auto_importance == 1.0

    def test_importance_clamped_negative(self, service):
        data = {
            "tags": [],
            "class": "notes",
            "summary": "test",
            "importance": -1.0,
        }
        result = service._parse_response(json.dumps(data))
        assert result.auto_importance == 0.0

    def test_null_summary_normalised(self, service):
        data = {
            "tags": [],
            "class": "notes",
            "summary": "null",
            "importance": 0.5,
        }
        result = service._parse_response(json.dumps(data))
        assert result.auto_summary is None


# ---------------------------------------------------------------------------
# enrich (async)
# ---------------------------------------------------------------------------


class TestEnrich:
    @pytest.fixture
    def mock_llm(self):
        return AsyncMock(return_value=VALID_JSON)

    @pytest.fixture
    def service(self, mock_llm):
        return EnrichmentService(llm=mock_llm)

    async def test_enrich_success(self, service, mock_llm):
        result = await service.enrich(
            content="Some content about Python ML.",
            title="ML Paper",
            existing_tags=["ai"],
        )
        assert result.success is True
        assert result.auto_tags == ["python", "machine-learning"]
        assert result.auto_class == "research"
        assert result.raw_response == VALID_JSON
        mock_llm.assert_awaited_once()

    async def test_enrich_llm_error(self):
        llm = AsyncMock(side_effect=RuntimeError("LLM down"))
        service = EnrichmentService(llm=llm)
        result = await service.enrich(content="test content")
        assert result.success is False
        assert "LLM down" in result.error

    async def test_enrich_truncates_long_content(self, mock_llm):
        service = EnrichmentService(llm=mock_llm, max_content_length=10)
        await service.enrich(content="A" * 100)
        call_kwargs = mock_llm.call_args.kwargs
        assert "[Content truncated...]" in call_kwargs["user_prompt"]


# ---------------------------------------------------------------------------
# batch_enrich
# ---------------------------------------------------------------------------


class TestBatchEnrich:
    async def test_batch_enrich_multiple(self):
        llm = AsyncMock(return_value=VALID_JSON)
        service = EnrichmentService(llm=llm)
        items = [
            {"content": "Item 1", "title": "T1"},
            {"content": "Item 2", "title": "T2"},
            {"content": "Item 3", "title": "T3"},
        ]
        results = await service.batch_enrich(items, concurrency=2)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert llm.await_count == 3

    async def test_batch_enrich_with_error(self):
        call_count = 0

        async def flaky_llm(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                msg = "boom"
                raise RuntimeError(msg)
            return VALID_JSON

        service = EnrichmentService(llm=flaky_llm)
        items = [
            {"content": "ok1", "title": "T1"},
            {"content": "fail", "title": "T2"},
            {"content": "ok2", "title": "T3"},
        ]
        results = await service.batch_enrich(items)
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
