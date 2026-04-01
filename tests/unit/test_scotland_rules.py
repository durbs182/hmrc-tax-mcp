"""Tests for the Scottish income tax rules (Phase 7)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule_snapshot, list_rules
from hmrc_tax_mcp.validation.pipeline import load_worked_examples, validate_rule

# ---------------------------------------------------------------------------
# Registry — Scotland jurisdiction presence
# ---------------------------------------------------------------------------

class TestScotlandRegistry:
    def test_list_rules_includes_scotland_income_tax_bands(self) -> None:
        rules = list_rules()
        found = [
            r for r in rules if r.rule_id == "income_tax_bands" and r.jurisdiction == "scotland"
        ]
        assert len(found) >= 1

    def test_scotland_rules_have_correct_jurisdiction(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        for rule in snapshot:
            assert rule.jurisdiction == "scotland"

    def test_scotland_snapshot_contains_income_tax_bands(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        ids = {r.rule_id for r in snapshot}
        assert "income_tax_bands" in ids

    def test_scotland_snapshot_contains_pa_taper(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        ids = {r.rule_id for r in snapshot}
        assert "pa_taper" in ids

    def test_scotland_snapshot_contains_savings_allowances(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        ids = {r.rule_id for r in snapshot}
        assert "savings_allowance_basic" in ids
        assert "savings_allowance_higher" in ids

    def test_scotland_snapshot_contains_dividend_allowance(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        ids = {r.rule_id for r in snapshot}
        assert "dividend_allowance" in ids

    def test_scotland_and_ruk_income_tax_bands_are_different(self) -> None:
        scotland = get_rule_snapshot("2025-26", "scotland")
        ruk = get_rule_snapshot("2025-26", "rUK")
        scot_itb = next(r for r in scotland if r.rule_id == "income_tax_bands")
        ruk_itb = next(r for r in ruk if r.rule_id == "income_tax_bands")
        # Different checksums — different band structures
        assert scot_itb.checksum != ruk_itb.checksum

    def test_get_rule_by_jurisdiction_scotland(self) -> None:
        # get_rule returns latest regardless of jurisdiction — verify both exist
        all_rules = list_rules()
        scot_itb = [r for r in all_rules
                    if r.rule_id == "income_tax_bands" and r.jurisdiction == "scotland"]
        assert scot_itb, "No Scotland income_tax_bands found"

    def test_scotland_income_tax_bands_has_citations(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        itb = next(r for r in snapshot if r.rule_id == "income_tax_bands")
        assert len(itb.citations) >= 2

    def test_scotland_income_tax_bands_checksum_matches_ast(self) -> None:
        from hmrc_tax_mcp.ast.canonical import ast_checksum
        snapshot = get_rule_snapshot("2025-26", "scotland")
        itb = next(r for r in snapshot if r.rule_id == "income_tax_bands")
        assert ast_checksum(itb.ast) == itb.checksum


# ---------------------------------------------------------------------------
# Evaluator — Scottish income tax band computations (HMRC worked examples)
# ---------------------------------------------------------------------------

def _eval_scot_itb(taxable_income: Decimal) -> Decimal:
    snapshot = get_rule_snapshot("2025-26", "scotland")
    rule = next(r for r in snapshot if r.rule_id == "income_tax_bands")
    ev = Evaluator(variables={"taxable_income": taxable_income})
    return ev.eval(rule.ast)


class TestScotlandIncomeTaxBands:
    def test_income_within_personal_allowance_no_tax(self) -> None:
        assert _eval_scot_itb(Decimal("10000")) == Decimal("0.00")

    def test_starter_rate_only(self) -> None:
        # £14,000 gross: starter band = £14,000 - £12,570 = £1,430 at 19%
        # = 271.70
        assert _eval_scot_itb(Decimal("14000")) == Decimal("271.70")

    def test_basic_rate_band(self) -> None:
        # £25,000 gross: starter (£2,827 at 19% = 537.13) + basic (£9,603 at 20% = 1920.60)
        # = 2457.73
        assert _eval_scot_itb(Decimal("25000")) == Decimal("2457.73")

    def test_intermediate_rate_band(self) -> None:
        # £35,000 gross
        assert _eval_scot_itb(Decimal("35000")) == Decimal("4532.82")

    def test_higher_rate_band(self) -> None:
        # £60,000 gross
        assert _eval_scot_itb(Decimal("60000")) == Decimal("13213.80")

    def test_advanced_rate_band(self) -> None:
        # £90,000 gross
        assert _eval_scot_itb(Decimal("90000")) == Decimal("26263.80")

    def test_top_rate_band(self) -> None:
        # £150,000 gross
        assert _eval_scot_itb(Decimal("150000")) == Decimal("54009.60")

    def test_exactly_at_starter_upper_boundary(self) -> None:
        # At £15,397 — only starter band applies (no basic)
        # £15,397 - £12,570 = £2,827 at 19% = 537.13
        assert _eval_scot_itb(Decimal("15397")) == Decimal("537.13")

    def test_exactly_at_basic_upper_boundary(self) -> None:
        # At £27,491 — starter + basic, no intermediate
        # starter: £2,827 at 19% = 537.13
        # basic: £27,491 - £15,397 = £12,094 at 20% = 2418.80
        # total = 2955.93
        assert _eval_scot_itb(Decimal("27491")) == Decimal("2955.93")

    def test_exactly_at_intermediate_upper_boundary(self) -> None:
        # At £43,662
        # starter: 537.13, basic: 2418.80, intermediate: (43662-27491)*21% = 3395.91
        # total = 6351.84
        assert _eval_scot_itb(Decimal("43662")) == Decimal("6351.84")

    def test_scotland_higher_rate_higher_than_ruk_for_same_income(self) -> None:
        """Scotland's 42% higher rate vs rUK's 40% — Scottish tax should be higher."""
        income = Decimal("60000")
        scot_tax = _eval_scot_itb(income)
        # rUK for same income
        ruk_rules = get_rule_snapshot("2025-26", "rUK")
        ruk_itb = next(r for r in ruk_rules if r.rule_id == "income_tax_bands")
        ev = Evaluator(variables={"taxable_income": income})
        ruk_tax = ev.eval(ruk_itb.ast)
        assert scot_tax > ruk_tax

    def test_nil_rate_band_zero_tax(self) -> None:
        assert _eval_scot_itb(Decimal("0")) == Decimal("0")

    def test_output_is_decimal(self) -> None:
        result = _eval_scot_itb(Decimal("30000"))
        assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# Validation pipeline — Scotland rules
# ---------------------------------------------------------------------------

_WORKED_EXAMPLES_DIR = (
    Path(__file__).parent.parent / "worked_examples" / "2025-26" / "scotland"
)


class TestScotlandValidationPipeline:
    def _get_rule(self, rule_id: str):
        snapshot = get_rule_snapshot("2025-26", "scotland")
        return next(r for r in snapshot if r.rule_id == rule_id)

    def test_income_tax_bands_passes_stages_1_to_5(self) -> None:
        rule = self._get_rule("income_tax_bands")
        examples_path = _WORKED_EXAMPLES_DIR / "income_tax_bands.yaml"
        examples = load_worked_examples(examples_path)
        results = validate_rule(rule.model_dump(), examples)
        for stage in results[:5]:
            assert stage.passed, f"Stage {stage.stage.value} failed: {stage.message}"

    def test_pa_taper_passes_stages_1_to_5(self) -> None:
        rule = self._get_rule("pa_taper")
        examples_path = _WORKED_EXAMPLES_DIR / "pa_taper.yaml"
        examples = load_worked_examples(examples_path)
        results = validate_rule(rule.model_dump(), examples)
        for stage in results[:5]:
            assert stage.passed, f"Stage {stage.stage.value} failed: {stage.message}"

    def test_stage_6_fails_unreviewed_rules(self) -> None:
        rule = self._get_rule("income_tax_bands")
        results = validate_rule(rule.model_dump())
        stage6 = results[5]
        assert stage6.stage.value == "human_review"
        assert not stage6.passed

    def test_savings_allowance_basic_passes_execution(self) -> None:
        rule = self._get_rule("savings_allowance_basic")
        results = validate_rule(rule.model_dump())
        exec_stage = next(r for r in results if r.stage.value == "execution")
        assert exec_stage.passed

    def test_dividend_allowance_passes_execution(self) -> None:
        rule = self._get_rule("dividend_allowance")
        results = validate_rule(rule.model_dump())
        exec_stage = next(r for r in results if r.stage.value == "execution")
        assert exec_stage.passed


# ---------------------------------------------------------------------------
# Scotland vs rUK — structural differences
# ---------------------------------------------------------------------------

class TestScotlandVsRuk:
    def test_scotland_has_six_income_tax_bands(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        itb = next(r for r in snapshot if r.rule_id == "income_tax_bands")
        # bands node has 7 entries (including nil-rate)
        assert len(itb.ast["bands"]) == 7

    def test_ruk_has_four_income_tax_bands(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "rUK")
        itb = next(r for r in snapshot if r.rule_id == "income_tax_bands")
        assert len(itb.ast["bands"]) == 4

    def test_scotland_top_rate_is_48_percent(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "scotland")
        itb = next(r for r in snapshot if r.rule_id == "income_tax_bands")
        top_band = itb.ast["bands"][-1]
        assert top_band["rate"] == pytest.approx(0.48)

    def test_ruk_top_rate_is_45_percent(self) -> None:
        snapshot = get_rule_snapshot("2025-26", "rUK")
        itb = next(r for r in snapshot if r.rule_id == "income_tax_bands")
        top_band = itb.ast["bands"][-1]
        assert top_band["rate"] == pytest.approx(0.45)

    def test_pa_taper_same_for_scotland_and_ruk(self) -> None:
        scot = get_rule_snapshot("2025-26", "scotland")
        ruk = get_rule_snapshot("2025-26", "rUK")
        scot_pa = next(r for r in scot if r.rule_id == "pa_taper")
        ruk_pa = next(r for r in ruk if r.rule_id == "pa_taper")
        # Same DSL, same checksum
        assert scot_pa.checksum == ruk_pa.checksum
