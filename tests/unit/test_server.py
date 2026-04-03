"""Tests for server import safety and handler behaviour without optional MCP deps."""

from __future__ import annotations

import asyncio
import json

from hmrc_tax_mcp import server


def _call_tool(name: str, arguments: dict) -> dict:
    result = asyncio.run(server.handle_call_tool(name, arguments))
    assert len(result) == 1
    return json.loads(result[0].text)


class TestServerImport:
    def test_import_without_mcp_runtime_succeeds(self) -> None:
        assert hasattr(server, "handle_call_tool")

    def test_main_raises_runtime_error_when_mcp_missing(self) -> None:
        if server._MCP_AVAILABLE:
            return
        try:
            server.main()
        except RuntimeError as exc:
            assert "requires Python >=3.10" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected RuntimeError when MCP dependency is unavailable")


class TestServerHandlers:
    def test_compile_dsl_returns_structured_error_for_parse_failure(self) -> None:
        result = _call_tool("compile_dsl", {"dsl": "return if income > 1 then 2"})
        assert "error" in result
        assert "else" in result["error"]

    def test_explain_rule_handles_let_backed_rule(self) -> None:
        result = _call_tool(
            "explain_rule",
            {"rule_id": "income_tax_due", "jurisdiction": "rUK", "tax_year": "2026-27"},
        )
        assert "explanation" in result
        assert "where" in result["explanation"].lower()
