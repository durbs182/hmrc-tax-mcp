"""Unit tests for the rule registry store."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule, get_rule_snapshot, list_rules


def test_list_rules_returns_list() -> None:
    rules = list_rules()
    assert isinstance(rules, list)


def test_list_rules_contains_2025_26_rules() -> None:
    rules = list_rules()
    ids = {r.rule_id for r in rules}
    expected = {
        "income_tax_bands",
        "pa_taper",
        "cgt_exempt",
        "cgt_rates",
        "pension_lsa",
        "pension_ufpls_tax_free_fraction",
        "pension_ufpls_taxable_fraction",
        "state_pension_annual",
        "savings_allowance_basic",
        "savings_allowance_higher",
        "dividend_allowance",
    }
    assert expected.issubset(ids)


def test_get_rule_missing_returns_none() -> None:
    assert get_rule("nonexistent.rule", "1.0.0") is None


def test_get_rule_latest_missing_returns_none() -> None:
    assert get_rule("nonexistent.rule") is None


def test_get_rule_snapshot_returns_list() -> None:
    result = get_rule_snapshot("2025-26", "rUK")
    assert isinstance(result, list)


def test_get_rule_snapshot_contains_all_ruk_2025_26() -> None:
    result = get_rule_snapshot("2025-26", "rUK")
    ids = {r.rule_id for r in result}
    assert "income_tax_bands" in ids
    assert "pa_taper" in ids
    assert len(result) >= 11


def test_income_tax_bands_rule_checksum() -> None:
    entry = get_rule("income_tax_bands", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "93d28d83674a1701a057e7bb8448977daeb9cbb233fe15fc058ee4c8070f4a88"


def test_pa_taper_rule_checksum() -> None:
    entry = get_rule("pa_taper")
    assert entry is not None
    assert entry.checksum == "a4f5132af3452c998f5175aa6f2df0049f1ff6d2cf2e0040dfa7a950ad5b00f8"


def test_pension_lsa_evaluates_correctly() -> None:
    entry = get_rule("pension_lsa")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("268275")


def test_cgt_exempt_evaluates_correctly() -> None:
    entry = get_rule("cgt_exempt")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("3000")


def test_income_tax_bands_evaluates_basic_rate() -> None:
    """£30,000 taxable income → £3,486 tax (20% on £17,430 above nil band)."""
    entry = get_rule("income_tax_bands", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"taxable_income": Decimal("30000")}).eval(entry.ast)
    assert result == Decimal("3486")


def test_pa_taper_evaluates_partial_taper() -> None:
    """Income £110,000 → PA tapered to £7,570 (£10,000 excess → £5,000 reduction)."""
    entry = get_rule("pa_taper")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("110000")}).eval(entry.ast)
    assert result == Decimal("7570")


def test_cgt_rates_higher_rate() -> None:
    entry = get_rule("cgt_rates")
    assert entry is not None
    result = Evaluator(variables={"is_higher_rate_taxpayer": True}).eval(entry.ast)
    assert result == Decimal("24")


def test_cgt_rates_basic_rate() -> None:
    entry = get_rule("cgt_rates")
    assert entry is not None
    result = Evaluator(variables={"is_higher_rate_taxpayer": False}).eval(entry.ast)
    assert result == Decimal("18")


def test_state_pension_annual() -> None:
    entry = get_rule("state_pension_annual")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("11502.40")

