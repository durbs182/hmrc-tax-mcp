"""Tests for P2 Bucket F/G/H property, pension accumulation and care rules."""

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


class TestSdltResidential:
    """SDLT on residential purchases in England and NI (2025-26 bands)."""

    def test_below_nil_band_zero_sdlt(self):
        assert _eval("sdlt_residential", {"purchase_price": 200000}) == Decimal("0.00")

    def test_exactly_at_nil_band_zero_sdlt(self):
        assert _eval("sdlt_residential", {"purchase_price": 250000}) == Decimal("0.00")

    def test_just_over_nil_band(self):
        """£300k — £50k in 5% band → £2,500."""
        assert _eval("sdlt_residential", {"purchase_price": 300000}) == Decimal("2500.00")

    def test_mid_range_property(self):
        """£600k — £350k in 5% band → £17,500."""
        assert _eval("sdlt_residential", {"purchase_price": 600000}) == Decimal("17500.00")

    def test_above_925k_threshold(self):
        """£1m: 5% on £675k = £33,750; 10% on £75k = £7,500 → £41,250."""
        assert _eval("sdlt_residential", {"purchase_price": 1000000}) == Decimal("41250.00")

    def test_above_1_5m_threshold(self):
        """£2m: 5%×£675k=£33,750; 10%×£575k=£57,500; 12%×£500k=£60,000 → £151,250."""
        assert _eval("sdlt_residential", {"purchase_price": 2000000}) == Decimal("151250.00")

    def test_all_years_same_checksum(self):
        base = get_rule("sdlt_residential", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("sdlt_residential", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestSdltHigherRates:
    """SDLT 5% surcharge for additional dwellings (from Oct 2024)."""

    def test_300k_second_home(self):
        assert _eval("sdlt_higher_rates", {"purchase_price": 300000}) == Decimal("15000.00")

    def test_500k_buy_to_let(self):
        assert _eval("sdlt_higher_rates", {"purchase_price": 500000}) == Decimal("25000.00")

    def test_total_sdlt_composition(self):
        """For a £300k additional dwelling: standard £2,500 + surcharge £15,000 = £17,500."""
        standard = _eval("sdlt_residential", {"purchase_price": 300000})
        surcharge = _eval("sdlt_higher_rates", {"purchase_price": 300000})
        assert standard + surcharge == Decimal("17500.00")

    def test_all_years_same_checksum(self):
        base = get_rule("sdlt_higher_rates", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("sdlt_higher_rates", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestIhtRnrbDownsizingAddition:
    def test_lost_rnrb_is_binding(self):
        """Lost RNRB £100k < qualifying estate £150k — addition £100,000."""
        result = _eval("iht_rnrb_downsizing_addition",
                       {"lost_rnrb_amount": 100000, "qualifying_estate_value": 150000})
        assert result == Decimal("100000.00")

    def test_qualifying_estate_is_binding(self):
        """Lost RNRB £175k > qualifying estate £50k — capped at £50,000."""
        result = _eval("iht_rnrb_downsizing_addition",
                       {"lost_rnrb_amount": 175000, "qualifying_estate_value": 50000})
        assert result == Decimal("50000.00")

    def test_no_qualifying_estate_zero(self):
        result = _eval("iht_rnrb_downsizing_addition",
                       {"lost_rnrb_amount": 175000, "qualifying_estate_value": 0})
        assert result == Decimal("0.00")

    def test_all_years_same_checksum(self):
        base = get_rule("iht_rnrb_downsizing_addition", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_rnrb_downsizing_addition", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionTaxReliefHigherRate:
    def test_higher_rate_taxpayer(self):
        """40% payer, £10k gross — additional 20% relief = £2,000."""
        result = _eval("pension_tax_relief_higher_rate",
                       {"marginal_rate": 0.40, "gross_contribution": 10000})
        assert result == Decimal("2000.00")

    def test_additional_rate_taxpayer(self):
        """45% payer, £10k gross — additional 25% relief = £2,500."""
        result = _eval("pension_tax_relief_higher_rate",
                       {"marginal_rate": 0.45, "gross_contribution": 10000})
        assert result == Decimal("2500.00")

    def test_basic_rate_payer_zero_additional(self):
        result = _eval("pension_tax_relief_higher_rate",
                       {"marginal_rate": 0.20, "gross_contribution": 10000})
        assert result == Decimal("0.00")

    def test_all_years_same_checksum(self):
        base = get_rule("pension_tax_relief_higher_rate", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_tax_relief_higher_rate", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestPensionNetPayArrangement:
    def test_basic_rate_net_pay(self):
        result = _eval("pension_net_pay_arrangement",
                       {"marginal_rate": 0.20, "gross_contribution": 5000})
        assert result == Decimal("1000.00")

    def test_higher_rate_net_pay(self):
        result = _eval("pension_net_pay_arrangement",
                       {"marginal_rate": 0.40, "gross_contribution": 5000})
        assert result == Decimal("2000.00")

    def test_all_years_same_checksum(self):
        base = get_rule("pension_net_pay_arrangement", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("pension_net_pay_arrangement", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestCareHomeCapitalThresholdEngland:
    def test_returns_23250(self):
        assert _eval("care_home_capital_threshold_england", {}) == Decimal("23250")

    def test_all_years_same_checksum(self):
        base = get_rule("care_home_capital_threshold_england",
                        jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("care_home_capital_threshold_england",
                         jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestCareHomeCapitalThresholdScotland:
    def test_returns_32750(self):
        assert _eval("care_home_capital_threshold_scotland", {},
                     jurisdiction="scotland") == Decimal("32750")

    def test_all_years_same_checksum(self):
        base = get_rule("care_home_capital_threshold_scotland",
                        jurisdiction="scotland", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("care_home_capital_threshold_scotland",
                         jurisdiction="scotland", tax_year=yr)
            assert e is not None and e.checksum == base.checksum
