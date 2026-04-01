"""Tests for NLExtractor and the extract_rule tool handler."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hmrc_tax_mcp.ast.canonical import ast_checksum
from hmrc_tax_mcp.dsl.compiler import compile_dsl
from hmrc_tax_mcp.extractor.nl_extractor import (
    ExtractionResult,
    NLExtractor,
    _parse_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_DSL = "return 3000"

_VALID_JSON_BLOCK = json.dumps({
    "rule_id": "test_exempt",
    "title": "Test Exemption",
    "description": "A simple constant rule.",
    "tax_year": "2025-26",
    "jurisdiction": "rUK",
    "citations": [{"title": "HMRC Test", "url": "https://hmrc.gov.uk/test", "section": "s1"}],
})

_VALID_RESPONSE = f"{_VALID_DSL}\n<<<JSON\n{_VALID_JSON_BLOCK}\nJSON>>>"


def _mock_anthropic(response_text: str):
    """Return a mock anthropic.Anthropic client whose create() returns response_text."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


# ---------------------------------------------------------------------------
# _parse_response unit tests
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_valid_response_extracts_dsl(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.dsl_source == _VALID_DSL

    def test_valid_response_extracts_rule_id(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.rule_id == "test_exempt"

    def test_valid_response_extracts_title(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.title == "Test Exemption"

    def test_valid_response_extracts_tax_year(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.tax_year == "2025-26"

    def test_valid_response_extracts_jurisdiction(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.jurisdiction == "rUK"

    def test_valid_response_extracts_citations(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert len(result.citations) == 1
        assert result.citations[0]["url"] == "https://hmrc.gov.uk/test"

    def test_valid_response_no_warnings(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.warnings == []

    def test_no_json_block_fallback(self) -> None:
        result = _parse_response("return 42")
        assert result.dsl_source == "return 42"
        assert result.rule_id == "unknown_rule"
        assert len(result.warnings) == 1
        assert "No JSON metadata" in result.warnings[0]

    def test_strips_markdown_fence(self) -> None:
        fenced = f"```dsl\n{_VALID_DSL}\n```\n<<<JSON\n{_VALID_JSON_BLOCK}\nJSON>>>"
        result = _parse_response(fenced)
        assert "```" not in result.dsl_source
        assert "return 3000" in result.dsl_source
        assert any("Markdown" in w for w in result.warnings)

    def test_bad_json_still_returns_dsl(self) -> None:
        bad = f"{_VALID_DSL}\n<<<JSON\n{{not valid json\nJSON>>>"
        result = _parse_response(bad)
        assert result.dsl_source == _VALID_DSL
        assert any("JSON parse error" in w for w in result.warnings)

    def test_raw_response_preserved(self) -> None:
        result = _parse_response(_VALID_RESPONSE)
        assert result.raw_response == _VALID_RESPONSE


# ---------------------------------------------------------------------------
# ExtractionResult tests
# ---------------------------------------------------------------------------

class TestExtractionResult:
    def _make(self, reviewed_by=None) -> ExtractionResult:
        return ExtractionResult(
            dsl_source=_VALID_DSL,
            rule_id="test_exempt",
            title="Test Exemption",
            description="A simple constant rule.",
            tax_year="2025-26",
            jurisdiction="rUK",
            citations=[],
            raw_response=_VALID_RESPONSE,
            reviewed_by=reviewed_by,
        )

    def test_requires_review_when_no_reviewer(self) -> None:
        assert self._make().requires_review is True

    def test_requires_review_false_when_reviewed(self) -> None:
        assert self._make(reviewed_by="engineer@example.com").requires_review is False

    def test_to_registry_dict_has_required_keys(self) -> None:
        d = self._make().to_registry_dict()
        for key in ("rule_id", "version", "title", "description", "tax_year",
                    "jurisdiction", "dsl_source", "reviewed_by", "citations", "provenance"):
            assert key in d

    def test_to_registry_dict_reviewed_by_none(self) -> None:
        d = self._make().to_registry_dict()
        assert d["reviewed_by"] is None

    def test_to_registry_dict_version_is_draft(self) -> None:
        d = self._make().to_registry_dict()
        assert d["version"] == "draft-0"

    def test_to_registry_dict_provenance_status(self) -> None:
        d = self._make().to_registry_dict()
        assert "DRAFT" in d["provenance"]["status"]


# ---------------------------------------------------------------------------
# NLExtractor.extract() — mocked API
# ---------------------------------------------------------------------------

class TestNLExtractorExtract:
    def _extractor(self, response_text: str) -> NLExtractor:
        extractor = NLExtractor(api_key="test-key")
        mock_client = _mock_anthropic(response_text)
        with patch("hmrc_tax_mcp.extractor.nl_extractor.NLExtractor._client",
                   return_value=mock_client):
            extractor._cached_client = mock_client
        return extractor

    def test_extract_returns_extraction_result(self) -> None:
        extractor = NLExtractor(api_key="test-key")
        mock_client = _mock_anthropic(_VALID_RESPONSE)
        with patch.object(extractor, "_client", return_value=mock_client):
            result = extractor.extract("The CGT annual exemption is £3,000.")
        assert isinstance(result, ExtractionResult)

    def test_extract_dsl_matches_response(self) -> None:
        extractor = NLExtractor(api_key="test-key")
        mock_client = _mock_anthropic(_VALID_RESPONSE)
        with patch.object(extractor, "_client", return_value=mock_client):
            result = extractor.extract("The CGT annual exemption is £3,000.")
        assert result.dsl_source == _VALID_DSL

    def test_extract_always_unreviewed(self) -> None:
        extractor = NLExtractor(api_key="test-key")
        mock_client = _mock_anthropic(_VALID_RESPONSE)
        with patch.object(extractor, "_client", return_value=mock_client):
            result = extractor.extract("Some HMRC text.")
        assert result.reviewed_by is None
        assert result.requires_review is True

    def test_extract_calls_anthropic_once(self) -> None:
        extractor = NLExtractor(api_key="test-key")
        mock_client = _mock_anthropic(_VALID_RESPONSE)
        with patch.object(extractor, "_client", return_value=mock_client):
            extractor.extract("Some HMRC text.")
        mock_client.messages.create.assert_called_once()

    def test_extract_passes_hmrc_text_in_message(self) -> None:
        extractor = NLExtractor(api_key="test-key")
        mock_client = _mock_anthropic(_VALID_RESPONSE)
        with patch.object(extractor, "_client", return_value=mock_client):
            extractor.extract("HMRC says X.")
        call_kwargs = mock_client.messages.create.call_args
        messages = (
            call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
            if call_kwargs.args
            else []
        )
        if not messages:
            messages = call_kwargs[1].get("messages", [])
        assert any("HMRC says X." in str(m) for m in messages)

    def test_import_error_if_anthropic_missing(self) -> None:
        extractor = NLExtractor(api_key="test-key")
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(ImportError, match="anthropic"):
                extractor._client()


# ---------------------------------------------------------------------------
# extract_rule tool handler (direct logic test — no MCP runtime)
# ---------------------------------------------------------------------------

def _json(data: Any) -> str:
    def _default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Not serialisable: {type(obj)}")
    return json.dumps(data, default=_default, indent=2)


def tool_extract_rule(hmrc_text: str, model: str = "claude-3-5-haiku-20241022",
                      mock_response: str = _VALID_RESPONSE) -> dict:
    """Replicate the server's extract_rule handler logic without MCP runtime."""
    from hmrc_tax_mcp.dsl.compiler import CompileError
    from hmrc_tax_mcp.dsl.tokenizer import TokenizeError
    from hmrc_tax_mcp.extractor.nl_extractor import NLExtractor

    extractor = NLExtractor(model=model, api_key="test-key")
    mock_client = _mock_anthropic(mock_response)
    with patch.object(extractor, "_client", return_value=mock_client):
        result = extractor.extract(hmrc_text)

    compile_error = None
    checksum = None
    ast_node = None
    try:
        ast_node = compile_dsl(result.dsl_source)
        checksum = ast_checksum(ast_node)
    except (CompileError, TokenizeError) as exc:
        compile_error = str(exc)

    return {
        "draft": result.to_registry_dict(),
        "dsl_source": result.dsl_source,
        "checksum": checksum,
        "ast": ast_node,
        "compile_error": compile_error,
        "warnings": result.warnings,
        "requires_review": result.requires_review,
        "review_instructions": (
            "This rule was generated by an LLM and has NOT been verified. "
            "You MUST check every value against the original HMRC source before "
            "adding it to the registry. Set reviewed_by to your name/email when done."
        ),
    }


class TestExtractRuleToolHandler:
    def test_returns_dsl_source(self) -> None:
        result = tool_extract_rule("The CGT exemption is £3,000.")
        assert result["dsl_source"] == _VALID_DSL

    def test_returns_requires_review_true(self) -> None:
        result = tool_extract_rule("Some text.")
        assert result["requires_review"] is True

    def test_returns_checksum_for_valid_dsl(self) -> None:
        result = tool_extract_rule("Some text.")
        assert result["checksum"] is not None
        assert len(result["checksum"]) == 64

    def test_compile_error_for_invalid_dsl(self) -> None:
        bad_response = f"not valid dsl !!!\n<<<JSON\n{_VALID_JSON_BLOCK}\nJSON>>>"
        result = tool_extract_rule("Some text.", mock_response=bad_response)
        assert result["compile_error"] is not None
        assert result["checksum"] is None

    def test_draft_has_reviewed_by_null(self) -> None:
        result = tool_extract_rule("Some text.")
        assert result["draft"]["reviewed_by"] is None

    def test_draft_has_rule_id(self) -> None:
        result = tool_extract_rule("Some text.")
        assert result["draft"]["rule_id"] == "test_exempt"

    def test_review_instructions_in_response(self) -> None:
        result = tool_extract_rule("Some text.")
        assert "MUST check" in result["review_instructions"]

    def test_no_warnings_for_clean_response(self) -> None:
        result = tool_extract_rule("Some text.")
        assert result["warnings"] == []

    def test_warning_for_missing_json_block(self) -> None:
        result = tool_extract_rule("Some text.", mock_response="return 42")
        assert any("No JSON metadata" in w for w in result["warnings"])
