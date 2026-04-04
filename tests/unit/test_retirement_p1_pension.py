"""
Tests for retirement P1 pension rules:
  - pension_annual_allowance (standard AA £60,000)
  - pension_commencement_lump_sum (25% PCLS, LSA-capped)
  - pension_lsa_remaining (LSA £268,275 minus prior tax-free cash)
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26") -> Decimal | bool:
    entry = get_rule(rule_id, jurisdiction="rUK", tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year}"
    return Evaluator(variables={k: Decimal(str(v)) for k, v in inputs.items()}).eval(entry.ast)


class TestPensionAnnualAllowance:
    """Standard AA: £60,000 across all years."""

    def test_returns_60000(self) -> None:
        assert _eval("pension_annual_allowance", {}) == Decimal("60000")

    def test_all_years_same(self) -> None:
        base = get_rule("pension_annual_allowance", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_annual_allowance", jurisdiction="rUK", tax_year=yr)
            assert e is not None, f"Missing rule for {yr}"
            assert e.checksum == base.checksum


class TestPensionCommencementLumpSum:
    """PCLS = min(crystallised × 25%, lsa_remaining), rounded to 2dp."""

    def test_normal_crystallisation(self) -> None:
        """£100k crystallised, full LSA → £25,000."""
        result = _eval("pension_commencement_lump_sum",
                       {"crystallised_amount": 100000, "lsa_remaining": 268275})
        assert result == Decimal("25000.00")

    def test_large_pot_within_lsa(self) -> None:
        """£800k crystallised, 25% = £200k < LSA → £200,000."""
        result = _eval("pension_commencement_lump_sum",
                       {"crystallised_amount": 800000, "lsa_remaining": 268275})
        assert result == Decimal("200000.00")

    def test_lsa_cap_applied(self) -> None:
        """£1.5m crystallised, 25% = £375k > LSA → capped at £268,275."""
        result = _eval("pension_commencement_lump_sum",
                       {"crystallised_amount": 1500000, "lsa_remaining": 268275})
        assert result == Decimal("268275.00")

    def test_partial_lsa_remaining(self) -> None:
        """£600k crystallised, only £100k LSA left → capped at £100,000."""
        result = _eval("pension_commencement_lump_sum",
                       {"crystallised_amount": 600000, "lsa_remaining": 100000})
        assert result == Decimal("100000.00")

    def test_lsa_exhausted(self) -> None:
        """LSA fully used → zero PCLS."""
        assert _eval("pension_commencement_lump_sum",
                     {"crystallised_amount": 200000, "lsa_remaining": 0}) == Decimal("0.00")

    def test_all_years_same_checksum(self) -> None:
        base = get_rule("pension_commencement_lump_sum", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_commencement_lump_sum", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"


class TestPensionLsaRemaining:
    """LSA remaining = max(268275 - prior_tax_free_cash, 0)."""

    def test_no_prior_crystallisation(self) -> None:
        assert _eval("pension_lsa_remaining", {"prior_tax_free_cash": 0}) == Decimal("268275")

    def test_partial_prior_cash(self) -> None:
        assert _eval("pension_lsa_remaining", {"prior_tax_free_cash": 100000}) == Decimal("168275")

    def test_fully_exhausted(self) -> None:
        assert _eval("pension_lsa_remaining", {"prior_tax_free_cash": 268275}) == Decimal("0")

    def test_floor_at_zero(self) -> None:
        """Prior cash > LSA (e.g. pre-2006 rights) → floored at 0."""
        assert _eval("pension_lsa_remaining", {"prior_tax_free_cash": 300000}) == Decimal("0")

    def test_pcls_and_lsa_remaining_compose(self) -> None:
        """PCLS on second crystallisation uses remaining LSA correctly."""
        # After first PCLS of £100k, LSA remaining = £168,275
        lsa_rem = _eval("pension_lsa_remaining", {"prior_tax_free_cash": 100000})
        # Second crystallisation of £200k: 25% = £50k < £168,275 → £50k
        pcls = _eval("pension_commencement_lump_sum",
                     {"crystallised_amount": 200000, "lsa_remaining": float(lsa_rem)})
        assert pcls == Decimal("50000.00")
