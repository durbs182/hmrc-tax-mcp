"""Tests for P3 Bucket A pension decumulation specialist rules."""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26", jurisdiction: str = "rUK"):
    entry = get_rule(rule_id, jurisdiction=jurisdiction, tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year} ({jurisdiction})"
    converted = {k: (v if isinstance(v, bool) else Decimal(str(v))) for k, v in inputs.items()}
    return Evaluator(variables=converted).eval(entry.ast)


class TestPensionCommencementExcessLumpSum:
    def test_40pct_marginal_rate(self):
        """£50k excess × 40% = £20,000 tax."""
        result = _eval(
            "pension_commencement_excess_lump_sum",
            {"excess_lump_sum": 50000, "marginal_rate": 0.40},
        )
        assert result == Decimal("20000.00")

    def test_45pct_marginal_rate(self):
        result = _eval(
            "pension_commencement_excess_lump_sum",
            {"excess_lump_sum": 100000, "marginal_rate": 0.45},
        )
        assert result == Decimal("45000.00")

    def test_zero_excess_zero_tax(self):
        result = _eval(
            "pension_commencement_excess_lump_sum",
            {"excess_lump_sum": 0, "marginal_rate": 0.40},
        )
        assert result == Decimal("0.00")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "pension_commencement_excess_lump_sum", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "pension_commencement_excess_lump_sum", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestPensionSeriousIllHealthLumpSum:
    def test_under_75_tax_free(self):
        """Age 74, terminal — lump sum is tax-free."""
        result = _eval(
            "pension_serious_ill_health_lump_sum",
            {"age": 74, "lump_sum_amount": 200000, "marginal_rate": 0.40},
        )
        assert result == Decimal("0.00")

    def test_exactly_75_taxable(self):
        """Age 75+ — lump sum taxed at marginal rate."""
        result = _eval(
            "pension_serious_ill_health_lump_sum",
            {"age": 75, "lump_sum_amount": 200000, "marginal_rate": 0.40},
        )
        assert result == Decimal("80000.00")

    def test_over_75_taxable(self):
        result = _eval(
            "pension_serious_ill_health_lump_sum",
            {"age": 82, "lump_sum_amount": 100000, "marginal_rate": 0.20},
        )
        assert result == Decimal("20000.00")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "pension_serious_ill_health_lump_sum", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "pension_serious_ill_health_lump_sum", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestPensionDeathBenefitLumpSum:
    def test_pre75_within_lsa_no_tax(self):
        """Died at 70, lump sum within LSA remaining — no tax."""
        result = _eval(
            "pension_death_benefit_lump_sum",
            {
                "age_at_death": 70,
                "lump_sum_amount": 200000,
                "lsa_remaining": 268275,
                "marginal_rate": 0.40,
            },
        )
        assert result == Decimal("0.00")

    def test_pre75_exceeds_lsa(self):
        """Died at 70, lump sum £300k, LSA remaining £268,275 — excess £31,725 × 40% = £12,690."""
        result = _eval(
            "pension_death_benefit_lump_sum",
            {
                "age_at_death": 70,
                "lump_sum_amount": 300000,
                "lsa_remaining": 268275,
                "marginal_rate": 0.40,
            },
        )
        assert result == Decimal("12690.00")

    def test_post75_all_taxable(self):
        """Died at 76 — full amount taxed at recipient's marginal rate."""
        result = _eval(
            "pension_death_benefit_lump_sum",
            {
                "age_at_death": 76,
                "lump_sum_amount": 200000,
                "lsa_remaining": 268275,
                "marginal_rate": 0.20,
            },
        )
        assert result == Decimal("40000.00")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "pension_death_benefit_lump_sum", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "pension_death_benefit_lump_sum", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestPensionEstateInclusion2027:
    def test_pre_2027_zero(self):
        result = _eval(
            "pension_estate_inclusion_2027",
            {"is_2027_or_later": False, "pension_pot_value": 500000},
        )
        assert result == Decimal("0")

    def test_2027_or_later_includes_pot(self):
        result = _eval(
            "pension_estate_inclusion_2027",
            {"is_2027_or_later": True, "pension_pot_value": 500000},
        )
        assert result == Decimal("500000")

    def test_zero_pot_returns_zero(self):
        result = _eval(
            "pension_estate_inclusion_2027",
            {"is_2027_or_later": True, "pension_pot_value": 0},
        )
        assert result == Decimal("0")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "pension_estate_inclusion_2027", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "pension_estate_inclusion_2027", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum
