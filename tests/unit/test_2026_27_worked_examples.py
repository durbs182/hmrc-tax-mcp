"""Validate all 2026-27 worked examples against the 2026-27 registry rules."""

from __future__ import annotations

from pathlib import Path

from hmrc_tax_mcp.registry.store import get_rule_snapshot
from hmrc_tax_mcp.validation.pipeline import load_worked_examples, validate_rule

_RUK_DIR = Path(__file__).parent.parent / "worked_examples" / "2026-27" / "ruk"
_SCOT_DIR = Path(__file__).parent.parent / "worked_examples" / "2026-27" / "scotland"


def _ruk_rule(rule_id: str) -> dict:
    snapshot = get_rule_snapshot("2026-27", "rUK")
    rule = next((r for r in snapshot if r.rule_id == rule_id), None)
    assert rule is not None, f"Rule {rule_id!r} not found in 2026-27 rUK snapshot"
    return rule.model_dump()


def _scot_rule(rule_id: str) -> dict:
    snapshot = get_rule_snapshot("2026-27", "scotland")
    rule = next((r for r in snapshot if r.rule_id == rule_id), None)
    assert rule is not None, f"Rule {rule_id!r} not found in 2026-27 scotland snapshot"
    return rule.model_dump()


# ---------------------------------------------------------------------------
# rUK 2026-27 worked examples
# ---------------------------------------------------------------------------

class TestRuk202627WorkedExamples:
    def _assert_passes(self, rule_id: str, yaml_file: str) -> None:
        examples = load_worked_examples(_RUK_DIR / yaml_file)
        assert examples, f"No examples found in {yaml_file}"
        results = validate_rule(_ruk_rule(rule_id), examples)
        stage5 = results[4]
        assert stage5.passed, (
            f"{rule_id} 2026-27 worked examples failed: {stage5.details}"
        )

    def test_income_tax_bands(self) -> None:
        self._assert_passes("income_tax_bands", "income_tax_bands.yaml")

    def test_pa_taper(self) -> None:
        self._assert_passes("pa_taper", "pa_taper.yaml")

    def test_cgt_rates(self) -> None:
        self._assert_passes("cgt_rates", "cgt_rates.yaml")

    def test_cgt_exempt(self) -> None:
        self._assert_passes("cgt_exempt", "cgt_exempt.yaml")

    def test_pension_lsa(self) -> None:
        self._assert_passes("pension_lsa", "pension_lsa.yaml")

    def test_pension_ufpls_tax_free_fraction(self) -> None:
        self._assert_passes(
            "pension_ufpls_tax_free_fraction", "pension_ufpls_tax_free_fraction.yaml"
        )

    def test_pension_ufpls_taxable_fraction(self) -> None:
        self._assert_passes(
            "pension_ufpls_taxable_fraction", "pension_ufpls_taxable_fraction.yaml"
        )


# ---------------------------------------------------------------------------
# Scotland 2026-27 worked examples
# ---------------------------------------------------------------------------

class TestScotland202627WorkedExamples:
    def _assert_passes(self, rule_id: str, yaml_file: str) -> None:
        examples = load_worked_examples(_SCOT_DIR / yaml_file)
        assert examples, f"No examples found in {yaml_file}"
        results = validate_rule(_scot_rule(rule_id), examples)
        stage5 = results[4]
        assert stage5.passed, (
            f"{rule_id} 2026-27 scotland worked examples failed: {stage5.details}"
        )

    def test_income_tax_bands(self) -> None:
        self._assert_passes("income_tax_bands", "income_tax_bands.yaml")

    def test_pa_taper(self) -> None:
        self._assert_passes("pa_taper", "pa_taper.yaml")
