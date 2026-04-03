"""
Tests for money_purchase_annual_allowance rule (2025-26 through 2030-31).

Money Purchase Annual Allowance (MPAA) rules (Finance (No. 2) Act 2023, effective 6 April 2023):
  - Triggered by: flexi-access drawdown, UFPLS, or income from a flexible annuity
  - MPAA (when triggered): £10,000 — caps all money-purchase pension contributions
  - Standard AA (when not triggered): £60,000 — normal limit applies
  - Alternative AA for DB when MPAA in force: £50,000 (£60,000 − £10,000, not computed here)
  - The £10,000 MPAA is unchanged from 2023-24 through 2030-31
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule


class TestMoneyPurchaseAnnualAllowance:
    """MPAA rule: correctness across both trigger states and all tax years."""

    def _eval(self, mpaa_triggered: bool, tax_year: str = "2025-26") -> Decimal:
        entry = get_rule("money_purchase_annual_allowance", jurisdiction="rUK",
                         tax_year=tax_year)
        assert entry is not None, f"Rule not found for {tax_year}"
        return Evaluator(
            variables={"mpaa_triggered": mpaa_triggered}
        ).eval(entry.ast)

    # ── Core logic ─────────────────────────────────────────────────────────

    def test_not_triggered_returns_standard_aa(self) -> None:
        """MPAA not triggered → standard Annual Allowance £60,000."""
        assert self._eval(False) == Decimal("60000")

    def test_triggered_returns_mpaa(self) -> None:
        """MPAA triggered → money-purchase contributions capped at £10,000."""
        assert self._eval(True) == Decimal("10000")

    def test_alternative_aa_implied(self) -> None:
        """When triggered, alternative AA for DB = standard AA − MPAA = £50,000."""
        standard_aa = self._eval(False)
        mpaa = self._eval(True)
        assert standard_aa - mpaa == Decimal("50000")

    # ── Frozen-year consistency ────────────────────────────────────────────

    def test_all_years_same_checksum(self) -> None:
        """MPAA frozen at £10,000 from 2025-26 through 2030-31 — identical checksums."""
        base = get_rule("money_purchase_annual_allowance", jurisdiction="rUK",
                        tax_year="2025-26")
        assert base is not None
        for yr in ("2026-27", "2027-28", "2028-29", "2029-30", "2030-31"):
            entry = get_rule("money_purchase_annual_allowance", jurisdiction="rUK",
                             tax_year=yr)
            assert entry is not None, f"Missing rule for {yr}"
            assert entry.checksum == base.checksum, f"Checksum mismatch for {yr}"

    def test_triggered_consistent_across_years(self) -> None:
        """Triggered MPAA is £10,000 in every registered year."""
        for yr in ("2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"):
            assert self._eval(True, tax_year=yr) == Decimal("10000"), \
                f"Unexpected MPAA for {yr}"

    def test_not_triggered_consistent_across_years(self) -> None:
        """Standard AA is £60,000 in every registered year when MPAA not in force."""
        for yr in ("2025-26", "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"):
            assert self._eval(False, tax_year=yr) == Decimal("60000"), \
                f"Unexpected standard AA for {yr}"

    # ── Scotland not applicable ────────────────────────────────────────────

    def test_not_available_for_scotland(self) -> None:
        """Pension AA is an HMRC rule; no Scotland-specific variant."""
        entry = get_rule("money_purchase_annual_allowance", jurisdiction="scotland",
                         tax_year="2025-26")
        assert entry is None
