"""Tests for P3 Bucket E IHT, F property, G accumulation, and H care specialist rules."""

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


class TestIhtCharityReducedRate:
    def test_10pct_to_charity_reduced_rate(self):
        """£40k charity on £400k net estate (exactly 10%) → 36%."""
        result = _eval(
            "iht_charity_reduced_rate",
            {"charity_amount": 40000, "net_estate": 400000},
        )
        assert result == Decimal("0.36")

    def test_more_than_10pct_reduced_rate(self):
        """£50k charity on £400k net estate (12.5%) → 36%."""
        result = _eval(
            "iht_charity_reduced_rate",
            {"charity_amount": 50000, "net_estate": 400000},
        )
        assert result == Decimal("0.36")

    def test_under_10pct_standard_rate(self):
        """£30k charity on £400k net estate (7.5%) → 40%."""
        result = _eval(
            "iht_charity_reduced_rate",
            {"charity_amount": 30000, "net_estate": 400000},
        )
        assert result == Decimal("0.40")

    def test_zero_charity_standard_rate(self):
        result = _eval(
            "iht_charity_reduced_rate",
            {"charity_amount": 0, "net_estate": 500000},
        )
        assert result == Decimal("0.40")

    def test_all_years_same_checksum(self):
        base = get_rule("iht_charity_reduced_rate", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_charity_reduced_rate", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestIhtBusinessPropertyRelief:
    def test_100pct_relief_unquoted_shares(self):
        """£500k unquoted shares at 100% BPR → £500,000 relief."""
        result = _eval(
            "iht_business_property_relief",
            {"asset_value": 500000, "relief_rate": 1.0},
        )
        assert result == Decimal("500000.00")

    def test_50pct_relief_quoted_shares(self):
        """£200k quoted minority shares at 50% BPR → £100,000 relief."""
        result = _eval(
            "iht_business_property_relief",
            {"asset_value": 200000, "relief_rate": 0.5},
        )
        assert result == Decimal("100000.00")

    def test_zero_asset_value(self):
        result = _eval(
            "iht_business_property_relief",
            {"asset_value": 0, "relief_rate": 1.0},
        )
        assert result == Decimal("0.00")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "iht_business_property_relief", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "iht_business_property_relief", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestIhtPensionEstateInclusion2027:
    def test_pre_2027_zero(self):
        result = _eval(
            "iht_pension_estate_inclusion_2027",
            {"is_2027_or_later": False, "pension_fund_value": 300000},
        )
        assert result == Decimal("0")

    def test_2027_or_later_includes_funds(self):
        result = _eval(
            "iht_pension_estate_inclusion_2027",
            {"is_2027_or_later": True, "pension_fund_value": 300000},
        )
        assert result == Decimal("300000")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "iht_pension_estate_inclusion_2027", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "iht_pension_estate_inclusion_2027", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestLbttResidential:
    def test_below_nil_band(self):
        """£100k purchase — below £145k nil band → £0."""
        result = _eval(
            "lbtt_residential", {"purchase_price": 100000}, jurisdiction="scotland"
        )
        assert result == Decimal("0.00")

    def test_exactly_at_nil_band(self):
        result = _eval(
            "lbtt_residential", {"purchase_price": 145000}, jurisdiction="scotland"
        )
        assert result == Decimal("0.00")

    def test_in_2pct_band(self):
        """£200k: 2% on £55k = £1,100."""
        result = _eval(
            "lbtt_residential", {"purchase_price": 200000}, jurisdiction="scotland"
        )
        assert result == Decimal("1100.00")

    def test_in_5pct_band(self):
        """£300k: 2% on £105k + 5% on £50k = £2,100 + £2,500 = £4,600."""
        result = _eval(
            "lbtt_residential", {"purchase_price": 300000}, jurisdiction="scotland"
        )
        assert result == Decimal("4600.00")

    def test_above_750k(self):
        """£800k: 2%×£105k + 5%×£75k + 10%×£425k + 12%×£50k =
        £2,100 + £3,750 + £42,500 + £6,000 = £54,350."""
        result = _eval(
            "lbtt_residential", {"purchase_price": 800000}, jurisdiction="scotland"
        )
        assert result == Decimal("54350.00")

    def test_all_years_same_checksum(self):
        base = get_rule("lbtt_residential", jurisdiction="scotland", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("lbtt_residential", jurisdiction="scotland", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionEmployerContribution:
    def test_employee_plus_employer(self):
        result = _eval(
            "pension_employer_contribution",
            {"employee_contribution": 10000, "employer_contribution": 5000},
        )
        assert result == Decimal("15000.00")

    def test_employer_only(self):
        result = _eval(
            "pension_employer_contribution",
            {"employee_contribution": 0, "employer_contribution": 60000},
        )
        assert result == Decimal("60000.00")

    def test_all_years_same_checksum(self):
        base = get_rule(
            "pension_employer_contribution", jurisdiction="rUK", tax_year="2025-26"
        )
        for yr in ALL_YEARS[1:]:
            e = get_rule(
                "pension_employer_contribution", jurisdiction="rUK", tax_year=yr
            )
            assert e is not None and e.checksum == base.checksum


class TestCareHomeNotionalCapital:
    def test_actual_plus_notional(self):
        """£10k actual + £50k notional (deprived) = £60,000 assessed capital."""
        result = _eval(
            "care_home_notional_capital",
            {"actual_capital": 10000, "notional_capital": 50000},
        )
        assert result == Decimal("60000.00")

    def test_no_notional_capital(self):
        result = _eval(
            "care_home_notional_capital",
            {"actual_capital": 25000, "notional_capital": 0},
        )
        assert result == Decimal("25000.00")

    def test_all_years_same_checksum(self):
        base = get_rule("care_home_notional_capital", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("care_home_notional_capital", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum
