"""
Tests for pension_tapered_annual_allowance rule (2025-26 through 2030-31).

Tapered Annual Allowance (TAA) rules (Finance (No. 2) Act 2023, effective 6 April 2023):
  - Standard Annual Allowance: £60,000
  - Threshold income limit: £200,000
  - Adjusted income limit: £260,000
  - Taper: £1 reduction per £2 of adjusted income above £260,000
  - Minimum tapered AA: £10,000 (reached at adjusted income of £360,000+)

Taper applies ONLY when BOTH threshold_income > £200,000 AND adjusted_income > £260,000.
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule


class TestPensionTaperedAnnualAllowance:
    """Tapered Annual Allowance rule: correctness across all scenarios."""

    def _eval(self, threshold_income: float, adjusted_income: float,
               tax_year: str = "2025-26") -> Decimal:
        entry = get_rule("pension_tapered_annual_allowance", jurisdiction="rUK",
                         tax_year=tax_year)
        assert entry is not None, f"Rule not found for {tax_year}"
        return Evaluator(
            variables={
                "threshold_income": Decimal(str(threshold_income)),
                "adjusted_income": Decimal(str(adjusted_income)),
            }
        ).eval(entry.ast)

    # ── Threshold income gate ──────────────────────────────────────────────

    def test_no_taper_low_threshold_income(self) -> None:
        """Threshold income £150k → taper gate not met → standard AA £60,000."""
        assert self._eval(150_000, 220_000) == Decimal("60000")

    def test_no_taper_threshold_exactly_200k(self) -> None:
        """Threshold income exactly £200,000 → gate is strictly >, so no taper."""
        assert self._eval(200_000, 300_000) == Decimal("60000")

    # ── Adjusted income gate ───────────────────────────────────────────────

    def test_no_taper_adjusted_exactly_260k(self) -> None:
        """Threshold > £200k but adjusted exactly £260k → no excess → standard AA £60,000."""
        assert self._eval(210_000, 260_000) == Decimal("60000")

    def test_no_taper_adjusted_below_260k(self) -> None:
        """Threshold > £200k but adjusted income £240k → below limit → £60,000."""
        assert self._eval(210_000, 240_000) == Decimal("60000")

    # ── Tapered amounts ────────────────────────────────────────────────────

    def test_tapered_adjusted_280k(self) -> None:
        """Adjusted £280k: excess=£20k, reduction=£10k → AA = £50,000."""
        # (280,000 - 260,000) / 2 = 10,000; 60,000 - 10,000 = 50,000
        assert self._eval(210_000, 280_000) == Decimal("50000")

    def test_tapered_adjusted_320k(self) -> None:
        """Adjusted £320k: excess=£60k, reduction=£30k → AA = £30,000."""
        assert self._eval(250_000, 320_000) == Decimal("30000")

    def test_tapered_adjusted_340k(self) -> None:
        """Adjusted £340k: excess=£80k, reduction=£40k → AA = £20,000."""
        assert self._eval(250_000, 340_000) == Decimal("20000")

    def test_tapered_adjusted_350k(self) -> None:
        """Adjusted £350k: excess=£90k, reduction=£45k → AA = £15,000."""
        assert self._eval(250_000, 350_000) == Decimal("15000")

    # ── Minimum floor ──────────────────────────────────────────────────────

    def test_minimum_floor_at_360k(self) -> None:
        """Adjusted £360k: reduction would be £50k → exactly at minimum → AA = £10,000."""
        # 60,000 - (100,000 / 2) = 60,000 - 50,000 = 10,000
        assert self._eval(300_000, 360_000) == Decimal("10000")

    def test_minimum_floor_above_360k(self) -> None:
        """Adjusted £400k: reduction would be £70k > standard AA → floored at £10,000."""
        assert self._eval(350_000, 400_000) == Decimal("10000")

    def test_minimum_floor_extreme_income(self) -> None:
        """Adjusted £1m: arithmetic would give negative; floor at £10,000."""
        assert self._eval(900_000, 1_000_000) == Decimal("10000")

    # ── Boundary cases ─────────────────────────────────────────────────────

    def test_just_above_threshold_income(self) -> None:
        """Threshold income £200,001 with adjusted £270k → taper applies."""
        # excess = max(270,000 - 260,000, 0) = 10,000; reduction = 5,000; AA = 55,000
        assert self._eval(200_001, 270_000) == Decimal("55000")

    def test_just_above_adjusted_income(self) -> None:
        """Adjusted £260,002 → excess=£2 → reduction=£1 → AA = £59,999."""
        assert self._eval(210_000, 260_002) == Decimal("59999")

    # ── Frozen-year consistency ────────────────────────────────────────────

    def test_all_years_same_checksum(self) -> None:
        """Thresholds frozen 2025-26 through 2030-31 — all years share the same checksum."""
        base = get_rule("pension_tapered_annual_allowance", jurisdiction="rUK",
                        tax_year="2025-26")
        assert base is not None
        for yr in ("2026-27", "2027-28", "2028-29", "2029-30", "2030-31"):
            entry = get_rule("pension_tapered_annual_allowance", jurisdiction="rUK",
                             tax_year=yr)
            assert entry is not None, f"Missing rule for {yr}"
            assert entry.checksum == base.checksum, f"Checksum mismatch for {yr}"

    def test_2026_27_matches_2025_26(self) -> None:
        """2026-27 rule gives same result as 2025-26 — thresholds unchanged."""
        r2526 = self._eval(250_000, 320_000, tax_year="2025-26")
        r2627 = self._eval(250_000, 320_000, tax_year="2026-27")
        assert r2526 == r2627 == Decimal("30000")

    def test_2030_31_still_correct(self) -> None:
        """Spot-check 2030-31 rule returns correct tapered amount."""
        assert self._eval(210_000, 280_000, tax_year="2030-31") == Decimal("50000")

    # ── Scotland not applicable ────────────────────────────────────────────

    def test_not_available_for_scotland(self) -> None:
        """Pension AA is an HMRC rule; no Scotland-specific variant."""
        entry = get_rule("pension_tapered_annual_allowance", jurisdiction="scotland",
                         tax_year="2025-26")
        assert entry is None
