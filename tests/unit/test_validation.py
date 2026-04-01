"""Tests for the 6-stage validation pipeline."""

from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from hmrc_tax_mcp.registry.store import get_rule, list_rules
from hmrc_tax_mcp.validation.pipeline import (
    ValidationStage,
    WorkedExample,
    load_worked_examples,
    validate_rule,
)

WORKED_EXAMPLES_DIR = (
    Path(__file__).parent.parent / "worked_examples" / "2025-26" / "ruk"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_dict(rule_id: str, jurisdiction: str = "rUK") -> dict[str, Any]:
    entry = get_rule(rule_id, jurisdiction=jurisdiction)
    assert entry is not None, f"Rule {rule_id!r} (jurisdiction={jurisdiction!r}) not found"
    return entry.model_dump()


def _run(rule_id: str, examples: list[WorkedExample] | None = None,
         jurisdiction: str = "rUK") -> list:
    return validate_rule(_rule_dict(rule_id, jurisdiction=jurisdiction), examples)


def _all_pass(results: list) -> bool:
    return all(r.passed for r in results)


# ---------------------------------------------------------------------------
# Stage 1 – Syntax
# ---------------------------------------------------------------------------

class TestStageSyntax:
    def test_valid_dsl_passes(self) -> None:
        results = _run("income_tax_bands")
        assert results[0].stage == ValidationStage.SYNTAX
        assert results[0].passed

    def test_empty_dsl_fails(self) -> None:
        rule = _rule_dict("income_tax_bands")
        rule["dsl_source"] = ""
        results = validate_rule(rule)
        assert not results[0].passed

    def test_broken_dsl_fails(self) -> None:
        rule = _rule_dict("income_tax_bands")
        rule["dsl_source"] = "let x = @@@ broken"
        results = validate_rule(rule)
        assert not results[0].passed

    def test_later_stages_skipped_on_syntax_failure(self) -> None:
        rule = _rule_dict("income_tax_bands")
        rule["dsl_source"] = "not valid dsl @@"
        results = validate_rule(rule)
        assert not results[0].passed
        # stages 2–6 should all be skipped
        for r in results[1:]:
            assert r.skipped, f"Expected skip, got: {r}"


# ---------------------------------------------------------------------------
# Stage 2 – Semantic
# ---------------------------------------------------------------------------

class TestStageSemantic:
    def test_valid_rule_passes(self) -> None:
        results = _run("cgt_exempt")
        assert results[1].passed

    def test_missing_field_fails(self) -> None:
        rule = _rule_dict("cgt_exempt")
        del rule["description"]
        results = validate_rule(rule)
        assert not results[1].passed
        assert "description" in results[1].details.get("missing", [])

    def test_invalid_provenance_fails(self) -> None:
        rule = _rule_dict("cgt_exempt")
        rule["provenance"] = "guessed"
        results = validate_rule(rule)
        assert not results[1].passed
        assert "guessed" in results[1].message

    def test_empty_citations_fails(self) -> None:
        rule = _rule_dict("cgt_exempt")
        rule["citations"] = []
        results = validate_rule(rule)
        assert not results[1].passed

    def test_malformed_citation_fails(self) -> None:
        rule = _rule_dict("cgt_exempt")
        rule["citations"] = [{"label": "Missing URL"}]
        results = validate_rule(rule)
        assert not results[1].passed


# ---------------------------------------------------------------------------
# Stage 3 – Canonicalisation
# ---------------------------------------------------------------------------

class TestStageCanonicalisation:
    def test_valid_checksum_passes(self) -> None:
        results = _run("pa_taper")
        assert results[2].passed

    def test_tampered_checksum_fails(self) -> None:
        rule = _rule_dict("pa_taper")
        rule["checksum"] = "0" * 64
        results = validate_rule(rule)
        assert not results[2].passed
        assert "mismatch" in results[2].message.lower()

    def test_tampered_dsl_fails(self) -> None:
        rule = _rule_dict("income_tax_bands")
        # Add an extra band that changes the AST
        rule["dsl_source"] = rule["dsl_source"].replace("at 45%", "at 50%")
        results = validate_rule(rule)
        assert not results[2].passed

    def test_all_ruk_rules_have_valid_checksums(self) -> None:
        for entry in list_rules():
            rule = entry.model_dump()
            results = validate_rule(rule)
            assert results[2].passed, (
                f"Checksum invalid for {entry.rule_id}: {results[2].message}"
            )


# ---------------------------------------------------------------------------
# Stage 4 – Execution
# ---------------------------------------------------------------------------

class TestStageExecution:
    def test_income_tax_bands_executes(self) -> None:
        results = _run("income_tax_bands")
        assert results[3].passed

    def test_pa_taper_executes(self) -> None:
        results = _run("pa_taper")
        assert results[3].passed

    def test_all_ruk_rules_execute(self) -> None:
        for entry in list_rules():
            rule = entry.model_dump()
            results = validate_rule(rule)
            assert results[3].passed, (
                f"Execution failed for {entry.rule_id}: {results[3].message}"
            )

    def test_bad_ast_fails(self) -> None:
        rule = _rule_dict("cgt_exempt")
        rule["ast"] = {"node": "UNKNOWN_NODE_TYPE"}
        results = validate_rule(rule)
        assert not results[3].passed


# ---------------------------------------------------------------------------
# Stage 5 – Worked examples
# ---------------------------------------------------------------------------

class TestStageWorkedExamples:
    def test_no_examples_passes_trivially(self) -> None:
        results = _run("income_tax_bands", examples=[])
        assert results[4].passed
        assert "skipped" in results[4].message.lower()

    def test_correct_example_passes(self) -> None:
        ex = WorkedExample(
            description="30k basic rate",
            inputs={"taxable_income": 30000},
            expected=3486,
        )
        results = _run("income_tax_bands", examples=[ex])
        assert results[4].passed

    def test_wrong_expected_fails(self) -> None:
        ex = WorkedExample(
            description="Wrong expected",
            inputs={"taxable_income": 30000},
            expected=9999,
        )
        results = _run("income_tax_bands", examples=[ex])
        assert not results[4].passed
        assert results[4].details["failures"]

    def test_income_tax_bands_all_worked_examples(self) -> None:
        examples = load_worked_examples(
            WORKED_EXAMPLES_DIR / "income_tax_bands.yaml"
        )
        assert len(examples) == 6
        results = _run("income_tax_bands", examples=examples)
        assert results[4].passed, results[4].details

    def test_pa_taper_all_worked_examples(self) -> None:
        examples = load_worked_examples(WORKED_EXAMPLES_DIR / "pa_taper.yaml")
        results = _run("pa_taper", examples=examples)
        assert results[4].passed, results[4].details

    def test_cgt_rates_worked_examples(self) -> None:
        examples = load_worked_examples(WORKED_EXAMPLES_DIR / "cgt_rates.yaml")
        results = _run("cgt_rates", examples=examples)
        assert results[4].passed, results[4].details

    def test_pension_lsa_worked_examples(self) -> None:
        examples = load_worked_examples(WORKED_EXAMPLES_DIR / "pension_lsa.yaml")
        results = _run("pension_lsa", examples=examples)
        assert results[4].passed, results[4].details

    def test_state_pension_worked_examples(self) -> None:
        examples = load_worked_examples(
            WORKED_EXAMPLES_DIR / "state_pension_annual.yaml"
        )
        results = _run("state_pension_annual", examples=examples)
        assert results[4].passed, results[4].details

    def test_tolerance_allows_rounding(self) -> None:
        ex = WorkedExample(
            description="With tolerance",
            inputs={"taxable_income": 30000},
            expected=3486.01,
            tolerance="0.10",
        )
        results = _run("income_tax_bands", examples=[ex])
        assert results[4].passed


# ---------------------------------------------------------------------------
# Stage 6 – Human review
# ---------------------------------------------------------------------------

class TestStageHumanReview:
    def test_unreviewed_rule_fails(self) -> None:
        # All current rules have reviewed_by=None
        results = _run("income_tax_bands")
        assert not results[5].passed
        assert "not been reviewed" in results[5].message

    def test_reviewed_rule_passes(self) -> None:
        rule = _rule_dict("income_tax_bands")
        rule["reviewed_by"] = "tax-expert@example.com"
        ex = WorkedExample(
            description="Smoke test",
            inputs={"taxable_income": 30000},
            expected=3486,
        )
        results = validate_rule(rule, worked_examples=[ex])
        assert results[5].passed
        assert "tax-expert@example.com" in results[5].message


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_all_stages_run_for_valid_rule(self) -> None:
        results = _run("cgt_exempt")
        assert len(results) == 6
        stages = [r.stage for r in results]
        expected_stages = list(ValidationStage)
        assert stages == expected_stages

    def test_full_pass_with_reviewed_by_and_examples(self) -> None:
        rule = _rule_dict("income_tax_bands")
        rule["reviewed_by"] = "auditor@hmrc.example"
        examples = load_worked_examples(
            WORKED_EXAMPLES_DIR / "income_tax_bands.yaml"
        )
        results = validate_rule(rule, worked_examples=examples)
        assert _all_pass(results), [
            f"{r.stage}: {r.message}" for r in results if not r.passed
        ]
