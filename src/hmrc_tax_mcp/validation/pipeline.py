"""
6-stage validation pipeline for HMRC tax rules.

Stages:
  1. Syntax          — DSL parses without error
  2. Semantic        — required fields present, types correct
  3. Canonicalisation — AST checksum matches stored checksum
  4. Execution        — rule evaluates without error on smoke-test inputs
  5. Worked examples  — outputs match HMRC-published examples (if provided)
  6. Human review     — rule has a non-null reviewed_by field

Each stage receives the full rule dict (as loaded from YAML / supplied by
caller). Stages run in order; if any stage fails, remaining stages are skipped
and returned as SKIPPED results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from hmrc_tax_mcp.ast.canonical import ast_checksum as _compute_ast_checksum
from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl
from hmrc_tax_mcp.dsl.tokenizer import TokenizeError
from hmrc_tax_mcp.evaluator import EvaluationError, Evaluator

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {
    "rule_id", "version", "tax_year", "jurisdiction",
    "title", "description", "dsl_source", "ast", "checksum",
    "citations", "provenance", "published_at",
}

_VALID_PROVENANCES = {"manual", "nl_extracted", "migrated"}


def _is_literal_two(arg: Any) -> bool:
    """Return True if the AST node or value represents the numeric literal 2."""
    # Handle plain Python numeric values directly.
    if isinstance(arg, (int, float, Decimal)):
        try:
            return Decimal(str(arg)) == Decimal("2")
        except Exception:
            return False

    # Handle common AST literal encodings, e.g. {"node": "NUMBER", "value": "2.00"}.
    if isinstance(arg, dict):
        if arg.get("node") in {"INT", "NUMBER", "DECIMAL", "LITERAL"}:
            value = arg.get("value")
            if isinstance(value, (int, float, Decimal)):
                try:
                    return Decimal(str(value)) == Decimal("2")
                except Exception:
                    return False
            if isinstance(value, str):
                try:
                    return Decimal(value) == Decimal("2")
                except Exception:
                    return False

    return False


def _final_result_is_rounded(ast: Any) -> bool:
    """Return True if the effective result of the AST is wrapped in round(expr, 2).

    Traverses LET bodies and IF branches so that wrapping patterns like
    ``let x = … in round(x, 2)`` are recognised. For IF nodes, both branches
    must be rounded to two decimal places.
    """
    if not isinstance(ast, dict):
        return False
    node = ast.get("node")
    if node == "CALL" and ast.get("name") == "round":
        # Enforce round(expr, 2): exactly two arguments and second is literal 2.
        args = ast.get("args") or ast.get("arguments")
        if isinstance(args, list) and len(args) == 2 and _is_literal_two(args[1]):
            return True
        return False
    if node == "LET":
        return _final_result_is_rounded(ast.get("body"))
    if node == "IF":
        return (
            _final_result_is_rounded(ast.get("then"))
            and _final_result_is_rounded(ast.get("else") or ast.get("else_"))
        )
    return False


class ValidationStage(str, Enum):
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    CANONICALISATION = "canonicalisation"
    EXECUTION = "execution"
    WORKED_EXAMPLES = "worked_examples"
    HUMAN_REVIEW = "human_review"


@dataclass
class ValidationResult:
    stage: ValidationStage
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def skipped(self) -> bool:
        return not self.passed and self.message.startswith("SKIPPED")


@dataclass
class WorkedExample:
    """A single input→expected-output pair used for stage-5 checks."""
    description: str
    inputs: dict[str, Any]
    expected: Any  # numeric or bool — compared with Decimal precision
    tolerance: str = "0"  # absolute Decimal tolerance (default: exact)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _skip(stage: ValidationStage, reason: str) -> ValidationResult:
    return ValidationResult(stage=stage, passed=False, message=f"SKIPPED: {reason}")


def _to_decimal(value: Any) -> Decimal:
    """Convert a Python value (int, float, bool, str, Decimal) to Decimal."""
    if isinstance(value, bool):
        return Decimal(1) if value else Decimal(0)
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

def _stage_syntax(rule: dict[str, Any]) -> ValidationResult:
    """Stage 1: DSL source must parse and compile to an AST without error."""
    dsl_source = rule.get("dsl_source", "")
    if not dsl_source or not dsl_source.strip():
        return ValidationResult(
            stage=ValidationStage.SYNTAX,
            passed=False,
            message="dsl_source is empty",
        )
    try:
        compile_dsl(dsl_source)
    except (CompileError, TokenizeError) as exc:
        return ValidationResult(
            stage=ValidationStage.SYNTAX,
            passed=False,
            message=f"DSL compilation error: {exc}",
        )
    return ValidationResult(
        stage=ValidationStage.SYNTAX,
        passed=True,
        message="DSL source compiles successfully",
    )


def _stage_semantic(rule: dict[str, Any]) -> ValidationResult:
    """Stage 2: Required fields present; provenance valid; citations non-empty."""
    missing = _REQUIRED_FIELDS - set(rule.keys())
    if missing:
        return ValidationResult(
            stage=ValidationStage.SEMANTIC,
            passed=False,
            message=f"Missing required fields: {sorted(missing)}",
            details={"missing": sorted(missing)},
        )

    provenance = rule.get("provenance", "")
    if provenance not in _VALID_PROVENANCES:
        return ValidationResult(
            stage=ValidationStage.SEMANTIC,
            passed=False,
            message=(
                f"Invalid provenance {provenance!r}; must be one of {sorted(_VALID_PROVENANCES)}"
            ),
        )

    citations = rule.get("citations") or []
    if not citations:
        return ValidationResult(
            stage=ValidationStage.SEMANTIC,
            passed=False,
            message="citations must contain at least one entry",
        )

    for i, cit in enumerate(citations):
        if not isinstance(cit, dict) or "label" not in cit or "url" not in cit:
            return ValidationResult(
                stage=ValidationStage.SEMANTIC,
                passed=False,
                message=f"Citation {i} missing 'label' or 'url'",
                details={"citation_index": i, "citation": cit},
            )

    if rule.get("monetary_output"):
        ast = rule.get("ast") or {}
        if not _final_result_is_rounded(ast):
            return ValidationResult(
                stage=ValidationStage.SEMANTIC,
                passed=False,
                message=(
                    "Rule declares monetary_output=true but the final result is not "
                    "wrapped in round(). Wrap the outermost expression in round(expr, 2) "
                    "per the rounding policy (docs/rules/rounding-policy.md)."
                ),
            )

    return ValidationResult(
        stage=ValidationStage.SEMANTIC,
        passed=True,
        message="All required fields present and valid",
    )


def _stage_canonicalisation(rule: dict[str, Any]) -> ValidationResult:
    """Stage 3: Recompile the DSL and verify both the stored AST and the
    recompiled AST produce the same checksum as the stored checksum."""
    dsl_source = rule.get("dsl_source", "")
    stored_checksum = rule.get("checksum", "")

    try:
        recompiled_ast = compile_dsl(dsl_source)
    except (CompileError, TokenizeError) as exc:
        return ValidationResult(
            stage=ValidationStage.CANONICALISATION,
            passed=False,
            message=f"Recompilation failed: {exc}",
        )

    computed = _compute_ast_checksum(recompiled_ast)
    if computed != stored_checksum:
        return ValidationResult(
            stage=ValidationStage.CANONICALISATION,
            passed=False,
            message="Checksum mismatch: recompiled DSL checksum differs from stored checksum",
            details={"stored": stored_checksum, "computed": computed},
        )

    # Also verify the stored AST itself checksums to the same value.
    # A tampered AST could pass the DSL-recompile check above while diverging
    # from what the DSL actually describes.
    stored_ast = rule.get("ast")
    if stored_ast is not None:
        stored_ast_checksum = _compute_ast_checksum(stored_ast)
        if stored_ast_checksum != stored_checksum:
            return ValidationResult(
                stage=ValidationStage.CANONICALISATION,
                passed=False,
                message=(
                    "Stored AST checksum does not match stored checksum — "
                    "AST may have been tampered with independently of the DSL"
                ),
                details={
                    "stored_checksum": stored_checksum,
                    "stored_ast_checksum": stored_ast_checksum,
                },
            )

    return ValidationResult(
        stage=ValidationStage.CANONICALISATION,
        passed=True,
        message=f"Checksum verified: {computed[:16]}…",
        details={"checksum": computed},
    )


def _stage_execution(rule: dict[str, Any]) -> ValidationResult:
    """Stage 4: AST evaluates without runtime error on a zero-input smoke test."""
    ast = rule.get("ast")
    if not isinstance(ast, dict):
        return ValidationResult(
            stage=ValidationStage.EXECUTION,
            passed=False,
            message="ast field is not a dict",
        )

    # Smoke test with all-zero numeric variables — we only check it doesn't crash.
    # Real correctness is verified by worked examples in stage 5.
    try:
        evaluator = Evaluator(variables=_zero_variables(ast))
        evaluator.eval(ast)
    except EvaluationError as exc:
        return ValidationResult(
            stage=ValidationStage.EXECUTION,
            passed=False,
            message=f"Execution error on smoke-test inputs: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(
            stage=ValidationStage.EXECUTION,
            passed=False,
            message=f"Unexpected error during execution: {exc}",
        )

    return ValidationResult(
        stage=ValidationStage.EXECUTION,
        passed=True,
        message="Rule executes without error on smoke-test inputs",
    )


def _zero_variables(ast: dict[str, Any]) -> dict[str, Any]:
    """Walk the AST and collect all VAR names; return them mapped to 0."""
    variables: dict[str, Any] = {}

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("node") == "VAR":
            variables[node["name"]] = Decimal(0)
        for v in node.values():
            if isinstance(v, dict):
                _walk(v)
            elif isinstance(v, list):
                for item in v:
                    _walk(item)

    _walk(ast)
    return variables


def _stage_worked_examples(
    rule: dict[str, Any],
    worked_examples: list[WorkedExample],
) -> ValidationResult:
    """Stage 5: Evaluate the AST against HMRC-published worked examples."""
    if not worked_examples:
        return ValidationResult(
            stage=ValidationStage.WORKED_EXAMPLES,
            passed=True,
            message="No worked examples provided — stage skipped (pass)",
        )

    ast = rule.get("ast")
    if ast is None:
        return ValidationResult(
            stage=ValidationStage.WORKED_EXAMPLES,
            passed=False,
            message="Rule has no compiled AST — cannot run worked examples",
        )
    failures: list[dict[str, Any]] = []

    for ex in worked_examples:
        variables = {k: _to_decimal(v) if not isinstance(v, bool) else v
                     for k, v in ex.inputs.items()}
        try:
            result = Evaluator(variables=variables).eval(ast)
        except EvaluationError as exc:
            failures.append({
                "description": ex.description,
                "error": str(exc),
            })
            continue

        expected = _to_decimal(ex.expected) if not isinstance(ex.expected, bool) else ex.expected
        tolerance = Decimal(ex.tolerance)

        if isinstance(expected, bool):
            if result != expected:
                failures.append({
                    "description": ex.description,
                    "expected": expected,
                    "got": result,
                })
        else:
            actual = _to_decimal(result)
            if abs(actual - expected) > tolerance:
                failures.append({
                    "description": ex.description,
                    "expected": str(expected),
                    "got": str(actual),
                    "tolerance": str(tolerance),
                })

    if failures:
        return ValidationResult(
            stage=ValidationStage.WORKED_EXAMPLES,
            passed=False,
            message=f"{len(failures)} of {len(worked_examples)} worked example(s) failed",
            details={"failures": failures},
        )

    return ValidationResult(
        stage=ValidationStage.WORKED_EXAMPLES,
        passed=True,
        message=f"All {len(worked_examples)} worked example(s) passed",
    )


def _stage_human_review(rule: dict[str, Any]) -> ValidationResult:
    """Stage 6: Rule must have a non-null reviewed_by field to be publication-ready."""
    reviewed_by = rule.get("reviewed_by")
    if not reviewed_by:
        return ValidationResult(
            stage=ValidationStage.HUMAN_REVIEW,
            passed=False,
            message="Rule has not been reviewed (reviewed_by is null) — not yet publication-ready",
        )
    return ValidationResult(
        stage=ValidationStage.HUMAN_REVIEW,
        passed=True,
        message=f"Rule reviewed by: {reviewed_by}",
        details={"reviewed_by": reviewed_by},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_rule(
    rule_dict: dict[str, Any],
    worked_examples: list[WorkedExample] | None = None,
) -> list[ValidationResult]:
    """
    Run the full 6-stage validation pipeline on a rule dict.

    Args:
        rule_dict: The rule as a plain dict (as loaded from YAML or the MCP tool).
        worked_examples: Optional list of WorkedExample instances for stage 5.
            If omitted, stage 5 passes trivially.

    Returns:
        A list of six ValidationResult instances, one per stage, in order.
        If an early stage fails, remaining stages are returned as SKIPPED.
    """
    stages = [
        (_stage_syntax, ValidationStage.SYNTAX),
        (_stage_semantic, ValidationStage.SEMANTIC),
        (_stage_canonicalisation, ValidationStage.CANONICALISATION),
        (_stage_execution, ValidationStage.EXECUTION),
    ]

    results: list[ValidationResult] = []
    failed = False

    for fn, stage in stages:
        if failed:
            results.append(_skip(stage, "earlier stage failed"))
        else:
            r = fn(rule_dict)
            results.append(r)
            if not r.passed:
                failed = True

    # Stage 5
    if failed:
        results.append(_skip(ValidationStage.WORKED_EXAMPLES, "earlier stage failed"))
    else:
        r5 = _stage_worked_examples(rule_dict, worked_examples or [])
        results.append(r5)
        if not r5.passed:
            failed = True

    # Stage 6
    if failed:
        results.append(_skip(ValidationStage.HUMAN_REVIEW, "earlier stage failed"))
    else:
        results.append(_stage_human_review(rule_dict))

    return results


def load_worked_examples(yaml_path: Path) -> list[WorkedExample]:
    """
    Load worked examples from a YAML file.

    Expected structure:
        examples:
          - description: "Basic rate taxpayer"
            inputs:
              taxable_income: 30000
            expected: 3486
            tolerance: "0"  # optional
    """
    with yaml_path.open() as fh:
        data = yaml.safe_load(fh)
    examples = []
    for item in data.get("examples", []):
        examples.append(WorkedExample(
            description=item["description"],
            inputs=item["inputs"],
            expected=item["expected"],
            tolerance=str(item.get("tolerance", "0")),
        ))
    return examples
