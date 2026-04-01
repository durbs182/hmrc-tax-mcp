"""Unit tests for the rule registry store."""

from __future__ import annotations

from hmrc_tax_mcp.registry.store import get_rule, get_rule_snapshot, list_rules


def test_list_rules_returns_list() -> None:
    rules = list_rules()
    assert isinstance(rules, list)


def test_get_rule_missing_returns_none() -> None:
    assert get_rule("nonexistent.rule", "1.0.0") is None


def test_get_rule_latest_missing_returns_none() -> None:
    assert get_rule("nonexistent.rule") is None


def test_get_rule_snapshot_returns_list() -> None:
    result = get_rule_snapshot("2025-26", "rUK")
    assert isinstance(result, list)
