"""
Tests for retirement P1 inheritance tax and state benefit rules:
  - iht_nil_rate_band (£325,000)
  - iht_residence_nil_rate_band (£175,000)
  - iht_due (40% on estate above NRB + RNRB)
  - iht_transferable_nil_rate_band (up to £650,000 for surviving spouse)
  - state_pension_weekly (2025-26: £230.25, 2026-27: £241.30)
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

ALL_YEARS = ["2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"]


def _eval(rule_id: str, inputs: dict, tax_year: str = "2025-26") -> Decimal:
    entry = get_rule(rule_id, jurisdiction="rUK", tax_year=tax_year)
    assert entry is not None, f"Rule {rule_id!r} not found for {tax_year}"
    return Evaluator(variables={k: Decimal(str(v)) for k, v in inputs.items()}).eval(entry.ast)


class TestIhtNilRateBand:
    """NRB frozen at £325,000 through 2030-31."""

    def test_returns_325000(self) -> None:
        assert _eval("iht_nil_rate_band", {}) == Decimal("325000")

    def test_all_years_same(self) -> None:
        base = get_rule("iht_nil_rate_band", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_nil_rate_band", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"


class TestIhtResidenceNilRateBand:
    """RNRB frozen at £175,000 through 2030-31."""

    def test_returns_175000(self) -> None:
        assert _eval("iht_residence_nil_rate_band", {}) == Decimal("175000")

    def test_all_years_same(self) -> None:
        base = get_rule("iht_residence_nil_rate_band", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_residence_nil_rate_band", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"

    def test_combined_threshold_with_nrb(self) -> None:
        """NRB + RNRB = £500,000 for a single estate."""
        nrb = _eval("iht_nil_rate_band", {})
        rnrb = _eval("iht_residence_nil_rate_band", {})
        assert nrb + rnrb == Decimal("500000")


class TestIhtDue:
    """IHT due = max(estate - nrb - rnrb, 0) × 40%, rounded to 2dp."""

    def test_estate_below_nrb_only(self) -> None:
        """£300k estate, NRB £325k → £0 IHT."""
        assert _eval("iht_due", {"estate_value": 300000, "nrb_available": 325000,
                                  "rnrb_available": 0}) == Decimal("0.00")

    def test_simple_estate_no_rnrb(self) -> None:
        """£600k estate, NRB £325k, no RNRB → 40% × £275k = £110,000."""
        assert _eval("iht_due", {"estate_value": 600000, "nrb_available": 325000,
                                  "rnrb_available": 0}) == Decimal("110000.00")

    def test_estate_with_rnrb(self) -> None:
        """£800k estate, NRB £325k, RNRB £175k → 40% × £300k = £120,000."""
        assert _eval("iht_due", {"estate_value": 800000, "nrb_available": 325000,
                                  "rnrb_available": 175000}) == Decimal("120000.00")

    def test_surviving_spouse_full_transfer(self) -> None:
        """£950k estate, NRB £650k, RNRB £350k (both transferred) → £0."""
        assert _eval("iht_due", {"estate_value": 950000, "nrb_available": 650000,
                                  "rnrb_available": 350000}) == Decimal("0.00")

    def test_large_estate(self) -> None:
        """£2m estate, NRB £325k, no RNRB → 40% × £1,675k = £670,000."""
        assert _eval("iht_due", {"estate_value": 2000000, "nrb_available": 325000,
                                  "rnrb_available": 0}) == Decimal("670000.00")

    def test_standard_nrb_rnrb_compose_with_iht_due(self) -> None:
        """Compose with iht_nil_rate_band and iht_residence_nil_rate_band rules."""
        nrb = _eval("iht_nil_rate_band", {})
        rnrb = _eval("iht_residence_nil_rate_band", {})
        iht = _eval("iht_due", {"estate_value": 700000,
                                 "nrb_available": float(nrb), "rnrb_available": float(rnrb)})
        # 40% × (700,000 - 325,000 - 175,000) = 40% × 200,000 = £80,000
        assert iht == Decimal("80000.00")

    def test_all_years_same_checksum(self) -> None:
        base = get_rule("iht_due", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_due", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"


class TestIhtTransferableNilRateBand:
    """Transferable NRB = £325,000 × (1 + unused_nrb_fraction)."""

    def test_full_transfer(self) -> None:
        """First spouse used none of NRB → £650,000."""
        assert _eval("iht_transferable_nil_rate_band",
                     {"unused_nrb_fraction": 1.0}) == Decimal("650000.0")

    def test_half_transfer(self) -> None:
        """50% unused → £325,000 + £162,500 = £487,500."""
        assert _eval("iht_transferable_nil_rate_band",
                     {"unused_nrb_fraction": 0.5}) == Decimal("487500.0")

    def test_no_transfer(self) -> None:
        """First spouse used all NRB → only own NRB £325,000."""
        assert _eval("iht_transferable_nil_rate_band",
                     {"unused_nrb_fraction": 0.0}) == Decimal("325000.0")

    def test_transferable_rnrb_doubles_combined_threshold(self) -> None:
        """With full NRB and RNRB both transferred: total threshold = £1,000,000."""
        tnrb = _eval("iht_transferable_nil_rate_band", {"unused_nrb_fraction": 1.0})
        rnrb = _eval("iht_residence_nil_rate_band", {})
        # Surviving spouse also gets transferred RNRB of £175k → total £350k
        assert tnrb + (rnrb * 2) == Decimal("1000000.0")

    def test_all_years_same_checksum(self) -> None:
        base = get_rule("iht_transferable_nil_rate_band", jurisdiction="rUK", tax_year="2025-26")
        assert base is not None
        for yr in ALL_YEARS[1:]:
            e = get_rule("iht_transferable_nil_rate_band", jurisdiction="rUK", tax_year=yr)
            assert e is not None and e.checksum == base.checksum, f"Mismatch for {yr}"


class TestStatePensionWeekly:
    """Full new State Pension weekly reference amounts."""

    def test_2025_26_rate(self) -> None:
        """2025-26: £230.25/week."""
        assert _eval("state_pension_weekly", {}, tax_year="2025-26") == Decimal("230.25")

    def test_2026_27_rate(self) -> None:
        """2026-27: £241.30/week."""
        assert _eval("state_pension_weekly", {}, tax_year="2026-27") == Decimal("241.30")

    def test_annual_weekly_relationship_2025_26(self) -> None:
        """Weekly × 52 must equal the annual amount from state_pension_annual."""
        weekly = _eval("state_pension_weekly", {}, tax_year="2025-26")
        annual_entry = get_rule("state_pension_annual", jurisdiction="rUK", tax_year="2025-26")
        assert annual_entry is not None
        annual = Evaluator(variables={}).eval(annual_entry.ast)
        assert weekly * 52 == annual

    def test_annual_weekly_relationship_2026_27(self) -> None:
        """2026-27: weekly × 52 = annual."""
        weekly = _eval("state_pension_weekly", {}, tax_year="2026-27")
        annual_entry = get_rule("state_pension_annual", jurisdiction="rUK", tax_year="2026-27")
        assert annual_entry is not None
        annual = Evaluator(variables={}).eval(annual_entry.ast)
        assert weekly * 52 == annual

    def test_not_available_for_2027_28(self) -> None:
        """Rates beyond 2026-27 are not pre-published — no rule registered."""
        entry = get_rule("state_pension_weekly", jurisdiction="rUK", tax_year="2027-28")
        assert entry is None

    def test_not_available_for_scotland(self) -> None:
        """State Pension is DWP-set (not devolved) — no Scotland variant."""
        entry = get_rule("state_pension_weekly", jurisdiction="scotland", tax_year="2025-26")
        assert entry is None
