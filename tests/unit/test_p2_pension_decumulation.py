"""Tests for P2 Bucket A pension decumulation rules."""

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


class TestPensionCarryForward:
    """pension_carry_forward: sum of unused AA over 3 prior years."""

    def test_all_years_fully_used_no_carry_forward(self):
        result = _eval("pension_carry_forward", {
            "annual_allowance": 60000, "pension_input_y1": 60000,
            "pension_input_y2": 60000, "pension_input_y3": 60000,
        })
        assert result == Decimal("0")

    def test_each_year_10k_unused(self):
        """3 × £10k unused = £30,000 carry forward."""
        result = _eval("pension_carry_forward", {
            "annual_allowance": 60000, "pension_input_y1": 50000,
            "pension_input_y2": 50000, "pension_input_y3": 50000,
        })
        assert result == Decimal("30000")

    def test_two_nil_years_one_full_year(self):
        """2 years nil input = 2 × £60k; 1 year fully used = £0 → £120,000."""
        result = _eval("pension_carry_forward", {
            "annual_allowance": 60000, "pension_input_y1": 60000,
            "pension_input_y2": 0, "pension_input_y3": 0,
        })
        assert result == Decimal("120000")

    def test_over_contribution_does_not_give_negative(self):
        """Pension input exceeds AA — unused floors at 0 per year."""
        result = _eval("pension_carry_forward", {
            "annual_allowance": 60000, "pension_input_y1": 80000,
            "pension_input_y2": 80000, "pension_input_y3": 80000,
        })
        assert result == Decimal("0")

    def test_mixed_years(self):
        """y1=£0 unused, y2=£20k unused, y3=£60k unused → £80,000."""
        result = _eval("pension_carry_forward", {
            "annual_allowance": 60000, "pension_input_y1": 60000,
            "pension_input_y2": 40000, "pension_input_y3": 0,
        })
        assert result == Decimal("80000")

    def test_all_years_same_checksum(self):
        base = get_rule("pension_carry_forward", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_carry_forward", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionAnnualAllowanceEffective:
    """pension_annual_allowance_effective: min of standard, tapered, MPAA."""

    def test_no_restrictions_standard_aa(self):
        result = _eval("pension_annual_allowance_effective", {
            "standard_annual_allowance": 60000,
            "tapered_annual_allowance": 60000,
            "mpaa_limit": 60000,
        })
        assert result == Decimal("60000")

    def test_taper_is_binding(self):
        result = _eval("pension_annual_allowance_effective", {
            "standard_annual_allowance": 60000,
            "tapered_annual_allowance": 30000,
            "mpaa_limit": 60000,
        })
        assert result == Decimal("30000")

    def test_mpaa_is_binding(self):
        result = _eval("pension_annual_allowance_effective", {
            "standard_annual_allowance": 60000,
            "tapered_annual_allowance": 20000,
            "mpaa_limit": 10000,
        })
        assert result == Decimal("10000")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "pension_annual_allowance_effective", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "pension_annual_allowance_effective", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestPensionSmallPotLumpSum:
    """pension_small_pot_lump_sum: 25% of pot value tax-free."""

    def test_max_small_pot(self):
        assert _eval("pension_small_pot_lump_sum", {"pot_value": 10000}) == Decimal("2500.00")

    def test_typical_small_pot(self):
        assert _eval("pension_small_pot_lump_sum", {"pot_value": 8000}) == Decimal("2000.00")

    def test_partial_pot(self):
        assert _eval("pension_small_pot_lump_sum", {"pot_value": 5500}) == Decimal("1375.00")

    def test_all_years_same_checksum(self):
        base = get_rule("pension_small_pot_lump_sum", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_small_pot_lump_sum", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionFlexiAccessTrigger:
    """pension_flexi_access_trigger: boolean MPAA trigger test."""

    def test_fad_triggers_mpaa(self):
        assert _eval("pension_flexi_access_trigger", {
            "is_flexi_access_drawdown": True, "is_ufpls": False, "is_flexible_annuity": False,
        }) is True

    def test_ufpls_triggers_mpaa(self):
        assert _eval("pension_flexi_access_trigger", {
            "is_flexi_access_drawdown": False, "is_ufpls": True, "is_flexible_annuity": False,
        }) is True

    def test_flexible_annuity_triggers_mpaa(self):
        assert _eval("pension_flexi_access_trigger", {
            "is_flexi_access_drawdown": False, "is_ufpls": False, "is_flexible_annuity": True,
        }) is True

    def test_pcls_only_no_trigger(self):
        assert _eval("pension_flexi_access_trigger", {
            "is_flexi_access_drawdown": False, "is_ufpls": False, "is_flexible_annuity": False,
        }) is False

    def test_all_years_same_checksum(self):
        base = get_rule("pension_flexi_access_trigger", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_flexi_access_trigger", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum
