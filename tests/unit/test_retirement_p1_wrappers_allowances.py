"""
Tests for retirement P1 ISA and income allowance rules:
  - isa_annual_allowance (£20,000)
  - isa_income_tax_due (zero — ISA income exempt)
  - isa_cgt_due (zero — ISA gains exempt)
  - marriage_allowance (£252 tax credit)
  - marriage_allowance_eligible (boolean eligibility test)
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26") -> Decimal | bool:
    entry = get_rule(rule_id, jurisdiction="rUK", tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year}"
    converted = {}
    for k, v in inputs.items():
        if isinstance(v, bool):
            converted[k] = v
        else:
            converted[k] = Decimal(str(v))
    return Evaluator(variables=converted).eval(entry.ast)


class TestIsaAnnualAllowance:
    """ISA subscription limit: £20,000 across all years."""

    def test_returns_20000(self) -> None:
        assert _eval("isa_annual_allowance", {}) == Decimal("20000")

    def test_all_years_same_checksum(self) -> None:
        base = get_rule("isa_annual_allowance", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("isa_annual_allowance", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"


class TestIsaIncomeTaxDue:
    """ISA income is fully exempt from income tax — rule returns 0."""

    def test_returns_zero(self) -> None:
        assert _eval("isa_income_tax_due", {}) == Decimal("0")

    def test_all_years_zero(self) -> None:
        for yr in ALL_YEARS:
            assert _eval("isa_income_tax_due", {}, tax_year=yr) == Decimal("0"), \
                f"Expected 0 for {yr}"


class TestIsaCgtDue:
    """ISA gains are fully exempt from CGT — rule returns 0."""

    def test_returns_zero(self) -> None:
        assert _eval("isa_cgt_due", {}) == Decimal("0")

    def test_all_years_zero(self) -> None:
        for yr in ALL_YEARS:
            assert _eval("isa_cgt_due", {}, tax_year=yr) == Decimal("0"), \
                f"Expected 0 for {yr}"

    def test_isa_income_and_cgt_share_same_zero_checksum(self) -> None:
        """Both ISA exemption rules use the same DSL (return 0) — same checksum."""
        it = get_rule("isa_income_tax_due", jurisdiction="rUK", tax_year="2025-26")
        cgt = get_rule("isa_cgt_due", jurisdiction="rUK", tax_year="2025-26")
        assert it is not None and cgt is not None
        assert it.checksum == cgt.checksum


class TestMarriageAllowance:
    """Marriage allowance tax credit: £252 across all years."""

    def test_returns_252(self) -> None:
        assert _eval("marriage_allowance", {}) == Decimal("252")

    def test_all_years_same(self) -> None:
        base = get_rule("marriage_allowance", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("marriage_allowance", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"

    def test_credit_is_20pct_of_transfer(self) -> None:
        """Credit (£252) = 10% of PA (£1,260 transfer) × 20% basic rate."""
        credit = _eval("marriage_allowance", {})
        assert credit == Decimal("1260") * Decimal("0.20")


class TestMarriageAllowanceEligible:
    """Boolean eligibility: transferor_income <= 12570 AND NOT recipient_is_higher_rate."""

    def test_eligible(self) -> None:
        result = _eval("marriage_allowance_eligible",
                       {"transferor_income": 10000, "recipient_is_higher_rate": False})
        assert result is True

    def test_transferor_income_at_pa_boundary(self) -> None:
        """Income exactly £12,570 — still eligible (<=, not <)."""
        result = _eval("marriage_allowance_eligible",
                       {"transferor_income": 12570, "recipient_is_higher_rate": False})
        assert result is True

    def test_transferor_income_above_pa(self) -> None:
        """Income £13,000 > PA → not eligible."""
        result = _eval("marriage_allowance_eligible",
                       {"transferor_income": 13000, "recipient_is_higher_rate": False})
        assert result is False

    def test_recipient_is_higher_rate(self) -> None:
        """Recipient is higher-rate taxpayer → not eligible."""
        result = _eval("marriage_allowance_eligible",
                       {"transferor_income": 10000, "recipient_is_higher_rate": True})
        assert result is False

    def test_both_conditions_fail(self) -> None:
        result = _eval("marriage_allowance_eligible",
                       {"transferor_income": 50000, "recipient_is_higher_rate": True})
        assert result is False

    def test_all_years_consistent(self) -> None:
        """PA frozen — eligibility rule identical across all years."""
        base = get_rule("marriage_allowance_eligible", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("marriage_allowance_eligible", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"
