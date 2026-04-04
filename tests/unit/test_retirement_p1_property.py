"""
Tests for retirement P1 property rules:
  - private_residence_relief (PRR: CGT exemption on main home)
  - prr_letting_relief (letting relief when shared occupancy with tenant)
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26") -> Decimal:
    entry = get_rule(rule_id, jurisdiction="rUK", tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year}"
    converted = {}
    for k, v in inputs.items():
        if isinstance(v, bool):
            converted[k] = v
        else:
            converted[k] = Decimal(str(v))
    return Evaluator(variables=converted).eval(entry.ast)


def _prr(gain: int, residence_months: int, total_months: int) -> Decimal:
    return _eval("private_residence_relief",
                 {"gain": gain,
                  "residence_months": residence_months,
                  "total_months": total_months})


def _letting(prr_amount: float, letting_gain: float, shared: bool) -> Decimal:
    return _eval("prr_letting_relief",
                 {"prr_amount": prr_amount,
                  "letting_gain": letting_gain,
                  "shared_occupancy": shared})


class TestPrivateResidenceRelief:
    """PRR = gain × min((residence_months + min(non-residence, 9)) / total_months, 1)."""

    def test_full_relief_always_main_residence(self) -> None:
        """120 months residence out of 120 total → 100% exempt."""
        assert _prr(200000, 120, 120) == Decimal("200000.00")

    def test_partial_relief_with_final_period(self) -> None:
        """60 months residence, 120 total: qualifying=69; 69/120 × £100k = £57,500."""
        assert _prr(100000, 60, 120) == Decimal("57500.00")

    def test_never_main_residence_final_period_only(self) -> None:
        """0 months residence, 120 total: qualifying=9; 9/120 × £200k = £15,000."""
        assert _prr(200000, 0, 120) == Decimal("15000.00")

    def test_near_full_relief(self) -> None:
        """108 months residence, 120 total: qualifying=117; 117/120 × £80k = £78,000."""
        assert _prr(80000, 108, 120) == Decimal("78000.00")

    def test_final_nine_months_not_added_beyond_total(self) -> None:
        """qualifying months capped at total — fraction never exceeds 1."""
        # residence=115, total=120: qualifying = 115 + min(5, 9) = 120; fraction = 1.0
        assert _prr(50000, 115, 120) == Decimal("50000.00")

    def test_short_ownership_period(self) -> None:
        """Owned 12 months, never resided: qualifying=9; 9/12=0.75; £100k × 0.75 = £75,000."""
        assert _prr(100000, 0, 12) == Decimal("75000.00")

    def test_zero_ownership_months_returns_zero(self) -> None:
        """total_months=0 guard — no division by zero, returns £0."""
        assert _prr(100000, 0, 0) == Decimal("0.00")

    def test_all_years_same_checksum(self) -> None:
        base = get_rule("private_residence_relief", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("private_residence_relief", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"


class TestPrrLettingRelief:
    """Letting relief: min(prr_amount, letting_gain, £40,000) — only if shared_occupancy."""

    def test_letting_gain_is_binding_cap(self) -> None:
        """PRR £50k, letting gain £30k, shared → relief = £30,000."""
        assert _letting(50000, 30000, True) == Decimal("30000.00")

    def test_statutory_40k_cap(self) -> None:
        """PRR £60k, letting gain £45k, shared → capped at £40,000."""
        assert _letting(60000, 45000, True) == Decimal("40000.00")

    def test_prr_is_binding_cap(self) -> None:
        """PRR £15k < letting gain £20k < £40k → capped at PRR = £15,000."""
        assert _letting(15000, 20000, True) == Decimal("15000.00")

    def test_no_shared_occupancy_zero_relief(self) -> None:
        """Post-April 2020: no shared occupancy → zero relief."""
        assert _letting(50000, 30000, False) == Decimal("0")

    def test_exactly_at_40k_cap(self) -> None:
        """Letting gain exactly £40k → relief = £40,000."""
        assert _letting(50000, 40000, True) == Decimal("40000.00")

    def test_letting_relief_after_prr_reduces_gain(self) -> None:
        """Compose PRR and letting relief: net chargeable = total - PRR - letting."""
        total_gain = Decimal("200000")
        # 60/120 months residence; qualifying=69; fraction=0.575; PRR = £115,000
        prr = _prr(200000, 60, 120)
        assert prr == Decimal("115000.00")
        letting_gain = total_gain - prr   # £85,000
        # min(£115k, £85k, £40k) = £40,000
        letting = _letting(float(prr), float(letting_gain), True)
        assert letting == Decimal("40000.00")
        # net chargeable = £200k - £115k - £40k = £45,000
        assert total_gain - prr - letting == Decimal("45000.00")

    def test_negative_inputs_clamped_to_zero(self) -> None:
        """Negative prr_amount or letting_gain must never return negative relief."""
        assert _letting(-1000, 5000, True) == Decimal("0")
        assert _letting(5000, -1000, True) == Decimal("0")

    def test_all_years_same_checksum(self) -> None:
        base = get_rule("prr_letting_relief", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("prr_letting_relief", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"
