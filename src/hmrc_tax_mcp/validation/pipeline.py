"""
6-stage validation pipeline for HMRC tax rules.

Stages:
  1. Syntax          — DSL parses without error
  2. Semantic        — required fields present, types correct
  3. Canonicalisation — AST checksum matches stored checksum
  4. Execution        — rule evaluates without error on test inputs
  5. Worked examples  — outputs match HMRC-published examples
  6. Human review     — rule is marked as reviewed before publication

Full implementation is a later phase; stubs are provided here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


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
    details: dict[str, Any] | None = None


def validate_rule(rule_dict: dict[str, Any]) -> list[ValidationResult]:
    """
    Run the full validation pipeline on a rule dict.

    Returns a list of ValidationResult for each stage.
    Stages are run in order; later stages are skipped if earlier ones fail.
    """
    results: list[ValidationResult] = []
    # Placeholder — full implementation in a later phase
    results.append(ValidationResult(
        stage=ValidationStage.SYNTAX,
        passed=True,
        message="Syntax validation not yet implemented (stub)",
    ))
    return results
