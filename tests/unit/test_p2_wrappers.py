"""Tests for P2 Bucket B tax-efficient wrapper rules."""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26"):
    entry = get_rule(rule_id, jurisdiction="rUK", tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year}"
    converted = {k: (v if isinstance(v, bool) else Decimal(str(v))) for k, v in inputs.items()}
    return Evaluator(variables=converted).eval(entry.ast)


class TestLifetimeIsaAnnualBonus:
    def test_full_4k_contribution(self):
        assert _eval("lifetime_isa_annual_bonus", {"contributions": 4000}) == Decimal("1000.00")

    def test_half_contribution(self):
        assert _eval("lifetime_isa_annual_bonus", {"contributions": 2000}) == Decimal("500.00")

    def test_exceeds_4k_capped(self):
        """£5,000 contributed — bonus capped based on £4,000 limit."""
        assert _eval("lifetime_isa_annual_bonus", {"contributions": 5000}) == Decimal("1000.00")

    def test_zero_contribution(self):
        assert _eval("lifetime_isa_annual_bonus", {"contributions": 0}) == Decimal("0.00")

    def test_all_years_same_checksum(self):
        base = get_rule("lifetime_isa_annual_bonus", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("lifetime_isa_annual_bonus", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestLifetimeIsaWithdrawalPenalty:
    def test_10k_withdrawal(self):
        result = _eval("lifetime_isa_withdrawal_penalty", {"withdrawal_amount": 10000})
        assert result == Decimal("2500.00")

    def test_5k_withdrawal(self):
        result = _eval("lifetime_isa_withdrawal_penalty", {"withdrawal_amount": 5000})
        assert result == Decimal("1250.00")

    def test_all_years_same_checksum(self):
        base = get_rule("lifetime_isa_withdrawal_penalty", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("lifetime_isa_withdrawal_penalty", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestInvestmentBondChargeableGain:
    def test_positive_gain(self):
        result = _eval("investment_bond_chargeable_gain",
                       {"proceeds": 150000, "total_premiums_paid": 100000})
        assert result == Decimal("50000.00")

    def test_loss_floored_at_zero(self):
        result = _eval("investment_bond_chargeable_gain",
                       {"proceeds": 80000, "total_premiums_paid": 100000})
        assert result == Decimal("0.00")

    def test_break_even_zero_gain(self):
        result = _eval("investment_bond_chargeable_gain",
                       {"proceeds": 100000, "total_premiums_paid": 100000})
        assert result == Decimal("0.00")

    def test_all_years_same_checksum(self):
        base = get_rule("investment_bond_chargeable_gain", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("investment_bond_chargeable_gain", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestInvestmentBondTopSlicingRelief:
    def test_typical_relief(self):
        """Full tax £4k, slice tax £2k, 10 years — relief £20,000."""
        result = _eval("investment_bond_top_slicing_relief",
                       {"full_tax_due": 4000, "tax_on_annual_slice": 2000, "policy_years": 10})
        assert result == Decimal("20000.00")

    def test_same_marginal_rate_zero_relief(self):
        result = _eval("investment_bond_top_slicing_relief",
                       {"full_tax_due": 2000, "tax_on_annual_slice": 2000, "policy_years": 5})
        assert result == Decimal("0.00")

    def test_single_year_policy(self):
        """1 year held — no spreading benefit."""
        result = _eval("investment_bond_top_slicing_relief",
                       {"full_tax_due": 3000, "tax_on_annual_slice": 2000, "policy_years": 1})
        assert result == Decimal("1000.00")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "investment_bond_top_slicing_relief", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "investment_bond_top_slicing_relief", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum
