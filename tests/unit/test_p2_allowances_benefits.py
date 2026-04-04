"""Tests for P2 Bucket C/D allowances and state benefits rules."""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26", jurisdiction: str = "rUK"):
    entry = get_rule(rule_id, jurisdiction=jurisdiction, tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year}"
    converted = {k: (v if isinstance(v, bool) else Decimal(str(v))) for k, v in inputs.items()}
    return Evaluator(variables=converted).eval(entry.ast)


class TestBlindPersonsAllowance:
    def test_returns_3070(self):
        assert _eval("blind_persons_allowance", {}) == Decimal("3070")

    def test_all_years_same_checksum(self):
        base = get_rule("blind_persons_allowance", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("blind_persons_allowance", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionCreditStandardMinimumGuarantee:
    def test_single_person(self):
        result = _eval("pension_credit_standard_minimum_guarantee", {"is_couple": False})
        assert result == Decimal("218.15")

    def test_couple(self):
        result = _eval("pension_credit_standard_minimum_guarantee", {"is_couple": True})
        assert result == Decimal("332.95")

    def test_all_years_same_checksum(self):
        base = get_rule("pension_credit_standard_minimum_guarantee",
                        jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_credit_standard_minimum_guarantee",
                         jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionCreditSavingsCredit:
    def test_post_2016_spa_returns_zero(self):
        """New SPA claimants (post-2016) not entitled to Savings Credit."""
        result = _eval("pension_credit_savings_credit", {
            "qualifying_income": 250.0, "is_couple": False, "reached_spa_before_2016": False,
        })
        assert result == Decimal("0")

    def test_pre_2016_spa_single_partial_credit(self):
        """Income £200/wk single: (200-174.49) × 0.6 = £15.31."""
        result = _eval("pension_credit_savings_credit", {
            "qualifying_income": 200.0, "is_couple": False, "reached_spa_before_2016": True,
        })
        assert result == Decimal("15.31")

    def test_pre_2016_spa_single_max_credit(self):
        """High income — capped at £17.29/week."""
        result = _eval("pension_credit_savings_credit", {
            "qualifying_income": 250.0, "is_couple": False, "reached_spa_before_2016": True,
        })
        assert result == Decimal("17.29")

    def test_pre_2016_spa_couple_max_credit(self):
        """High income couple — capped at £19.36/week."""
        result = _eval("pension_credit_savings_credit", {
            "qualifying_income": 500.0, "is_couple": True, "reached_spa_before_2016": True,
        })
        assert result == Decimal("19.36")

    def test_income_below_threshold_zero(self):
        """Income below threshold — credit £0."""
        result = _eval("pension_credit_savings_credit", {
            "qualifying_income": 100.0, "is_couple": False, "reached_spa_before_2016": True,
        })
        assert result == Decimal("0")

    def test_all_years_same_checksum(self):
        base = get_rule("pension_credit_savings_credit", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_credit_savings_credit", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum
