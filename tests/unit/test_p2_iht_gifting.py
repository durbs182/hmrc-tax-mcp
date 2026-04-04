"""Tests for P2 Bucket E IHT gifting rules."""

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


class TestIhtAnnualGiftExemption:
    def test_no_carry_forward(self):
        assert _eval("iht_annual_gift_exemption", {"prior_year_unused": False}) == Decimal("3000")

    def test_with_carry_forward(self):
        assert _eval("iht_annual_gift_exemption", {"prior_year_unused": True}) == Decimal("6000")

    def test_all_years_same_checksum(self):
        base = get_rule("iht_annual_gift_exemption", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_annual_gift_exemption", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestIhtSmallGiftsExemption:
    def test_returns_250(self):
        assert _eval("iht_small_gifts_exemption", {}) == Decimal("250")

    def test_all_years_same_checksum(self):
        base = get_rule("iht_small_gifts_exemption", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_small_gifts_exemption", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestIhtTaperRelief:
    def test_under_3_years_no_relief(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 2}) == Decimal("0")

    def test_exactly_3_years_20_percent(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 3}) == Decimal("20")

    def test_4_years_40_percent(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 4}) == Decimal("40")

    def test_5_years_60_percent(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 5}) == Decimal("60")

    def test_6_years_80_percent(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 6}) == Decimal("80")

    def test_7_years_fully_exempt(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 7}) == Decimal("100")

    def test_10_years_fully_exempt(self):
        assert _eval("iht_taper_relief", {"years_since_gift": 10}) == Decimal("100")

    def test_all_years_same_checksum(self):
        base = get_rule("iht_taper_relief", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_taper_relief", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestIhtPotentiallyExemptTransfer:
    def test_gift_within_nrb_zero_tax(self):
        """£200k gift with full NRB — no IHT."""
        result = _eval("iht_potentially_exempt_transfer", {
            "gift_amount": 200000, "nil_rate_band_remaining": 325000,
            "taper_relief_percentage": 0,
        })
        assert result == Decimal("0.00")

    def test_gift_above_nrb_no_taper(self):
        """£500k gift, no NRB left, no taper — 40% of £500k = £200,000."""
        result = _eval("iht_potentially_exempt_transfer", {
            "gift_amount": 500000, "nil_rate_band_remaining": 0,
            "taper_relief_percentage": 0,
        })
        assert result == Decimal("200000.00")

    def test_gift_with_taper(self):
        """£500k gift, full NRB, dies yr 5 (60% taper): 40%×£175k×40% = £28,000."""
        result = _eval("iht_potentially_exempt_transfer", {
            "gift_amount": 500000, "nil_rate_band_remaining": 325000,
            "taper_relief_percentage": 60,
        })
        assert result == Decimal("28000.00")

    def test_all_years_same_checksum(self):
        base = get_rule("iht_potentially_exempt_transfer", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_potentially_exempt_transfer", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum


class TestIhtNormalExpenditureIncome:
    def test_all_conditions_met_exempt(self):
        result = _eval("iht_normal_expenditure_income", {
            "is_habitual": True, "paid_from_income": True,
            "leaves_adequate_living_standard": True,
        })
        assert result is True

    def test_not_habitual_not_exempt(self):
        result = _eval("iht_normal_expenditure_income", {
            "is_habitual": False, "paid_from_income": True,
            "leaves_adequate_living_standard": True,
        })
        assert result is False

    def test_paid_from_capital_not_exempt(self):
        result = _eval("iht_normal_expenditure_income", {
            "is_habitual": True, "paid_from_income": False,
            "leaves_adequate_living_standard": True,
        })
        assert result is False

    def test_inadequate_living_standard_not_exempt(self):
        result = _eval("iht_normal_expenditure_income", {
            "is_habitual": True, "paid_from_income": True,
            "leaves_adequate_living_standard": False,
        })
        assert result is False

    def test_all_years_same_checksum(self):
        base = get_rule("iht_normal_expenditure_income", jurisdiction="rUK", tax_year="2025-26")
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_normal_expenditure_income", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum
