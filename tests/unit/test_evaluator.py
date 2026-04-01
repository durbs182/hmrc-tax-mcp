"""Unit tests for the AST evaluator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hmrc_tax_mcp.evaluator import EvaluationError, Evaluator


def ev(ast: dict, vars: dict | None = None) -> Decimal | bool:
    return Evaluator(variables=vars or {}).eval(ast)


class TestConst:
    def test_integer(self) -> None:
        assert ev({"node": "CONST", "value": 12570}) == Decimal("12570")

    def test_float(self) -> None:
        assert ev({"node": "CONST", "value": 0.20}) == Decimal("0.20")

    def test_zero(self) -> None:
        assert ev({"node": "CONST", "value": 0}) == Decimal("0")


class TestVar:
    def test_known_variable(self) -> None:
        result = ev({"node": "VAR", "name": "income"}, {"income": 50000})
        assert result == Decimal("50000")

    def test_unknown_variable_raises(self) -> None:
        with pytest.raises(EvaluationError, match="Unknown variable"):
            ev({"node": "VAR", "name": "missing"})


class TestArithmetic:
    def test_add(self) -> None:
        assert ev({"node": "ADD", "args": [
            {"node": "CONST", "value": 100},
            {"node": "CONST", "value": 50},
        ]}) == Decimal("150")

    def test_sub(self) -> None:
        assert ev({"node": "SUB", "args": [
            {"node": "CONST", "value": 100},
            {"node": "CONST", "value": 30},
        ]}) == Decimal("70")

    def test_mul(self) -> None:
        assert ev({"node": "MUL", "args": [
            {"node": "CONST", "value": 10},
            {"node": "CONST", "value": 3},
        ]}) == Decimal("30")

    def test_div(self) -> None:
        assert ev({"node": "DIV", "args": [
            {"node": "CONST", "value": 100},
            {"node": "CONST", "value": 4},
        ]}) == Decimal("25")

    def test_div_by_zero_raises(self) -> None:
        with pytest.raises(EvaluationError, match="Division by zero"):
            ev({"node": "DIV", "args": [
                {"node": "CONST", "value": 10},
                {"node": "CONST", "value": 0},
            ]})


class TestComparisons:
    def test_gt_true(self) -> None:
        assert ev({"node": "GT", "args": [
            {"node": "CONST", "value": 110000},
            {"node": "CONST", "value": 100000},
        ]}) is True

    def test_gt_false(self) -> None:
        assert ev({"node": "GT", "args": [
            {"node": "CONST", "value": 99999},
            {"node": "CONST", "value": 100000},
        ]}) is False

    def test_lte_equal(self) -> None:
        assert ev({"node": "LTE", "args": [
            {"node": "CONST", "value": 100000},
            {"node": "CONST", "value": 100000},
        ]}) is True

    def test_eq(self) -> None:
        assert ev({"node": "EQ", "args": [
            {"node": "CONST", "value": 12570},
            {"node": "CONST", "value": 12570},
        ]}) is True

    def test_neq(self) -> None:
        assert ev({"node": "NEQ", "args": [
            {"node": "CONST", "value": 1},
            {"node": "CONST", "value": 2},
        ]}) is True


class TestLogical:
    def test_and_both_true(self) -> None:
        assert ev({"node": "AND", "args": [
            {"node": "CONST", "value": 1},
            {"node": "CONST", "value": 1},
        ]}) is True

    def test_or_one_false(self) -> None:
        assert ev({"node": "OR", "args": [
            {"node": "CONST", "value": 0},
            {"node": "CONST", "value": 1},
        ]}) is True

    def test_not(self) -> None:
        assert ev({"node": "NOT", "args": [{"node": "CONST", "value": 0}]}) is True


class TestIf:
    def test_then_branch(self) -> None:
        result = ev({
            "node": "IF",
            "cond": {"node": "CONST", "value": 1},
            "then": {"node": "CONST", "value": 999},
            "else": {"node": "CONST", "value": 0},
        })
        assert result == Decimal("999")

    def test_else_branch(self) -> None:
        result = ev({
            "node": "IF",
            "cond": {"node": "CONST", "value": 0},
            "then": {"node": "CONST", "value": 999},
            "else": {"node": "CONST", "value": 42},
        })
        assert result == Decimal("42")


class TestLet:
    def test_let_binding(self) -> None:
        result = ev({
            "node": "LET",
            "bindings": {"pa": {"node": "CONST", "value": 12570}},
            "body": {"node": "VAR", "name": "pa"},
        })
        assert result == Decimal("12570")


class TestBandApply:
    """Progressive income tax — 2025-26 rUK bands applied to taxable income."""

    BANDS_AST: dict = {
        "node": "BAND_APPLY",
        "args": [{"node": "VAR", "name": "taxable_income"}],
        "bands": [
            {"lower": 0, "upper": 37700, "rate": 0.20},
            {"lower": 37700, "upper": 125140, "rate": 0.40},
            {"lower": 125140, "upper": None, "rate": 0.45},
        ],
    }

    def test_basic_rate_only(self) -> None:
        # £20,000 taxable → 20% × £20,000 = £4,000
        assert ev(self.BANDS_AST, {"taxable_income": 20000}) == Decimal("4000")

    def test_crosses_basic_higher_boundary(self) -> None:
        # £40,000: 20% × £37,700 + 40% × £2,300 = £7,540 + £920 = £8,460
        assert ev(self.BANDS_AST, {"taxable_income": 40000}) == Decimal("8460")

    def test_nil_income(self) -> None:
        assert ev(self.BANDS_AST, {"taxable_income": 0}) == Decimal("0")

    def test_additional_rate(self) -> None:
        # £130,000: basic+higher+additional
        # 20%×37700 + 40%×87440 + 45%×4860
        # = 7540 + 34976 + 2187 = 44703
        result = ev(self.BANDS_AST, {"taxable_income": 130000})
        assert result == Decimal("44703")


class TestTaper:
    """Personal allowance taper: £1 lost per £2 over £100,000."""

    TAPER_AST: dict = {
        "node": "TAPER",
        "args": [{"node": "VAR", "name": "adjusted_net_income"}],
        "threshold": {"node": "CONST", "value": 100000},
        "ratio": {"node": "CONST", "value": 0.5},
        "base": {"node": "CONST", "value": 12570},
    }

    def test_below_threshold_full_allowance(self) -> None:
        assert ev(self.TAPER_AST, {"adjusted_net_income": 99999}) == Decimal("12570")

    def test_at_threshold_full_allowance(self) -> None:
        assert ev(self.TAPER_AST, {"adjusted_net_income": 100000}) == Decimal("12570")

    def test_partially_tapered(self) -> None:
        # £110,000 → excess £10,000 → reduction £5,000 → allowance £7,570
        assert ev(self.TAPER_AST, {"adjusted_net_income": 110000}) == Decimal("7570")

    def test_fully_tapered(self) -> None:
        # £125,140 → excess £25,140 → reduction £12,570 → allowance £0
        assert ev(self.TAPER_AST, {"adjusted_net_income": 125140}) == Decimal("0")

    def test_above_taper_never_negative(self) -> None:
        assert ev(self.TAPER_AST, {"adjusted_net_income": 200000}) == Decimal("0")


class TestCall:
    def test_percent(self) -> None:
        result = ev({"node": "CALL", "name": "percent", "args": [
            {"node": "CONST", "value": 50000},
            {"node": "CONST", "value": 20},
        ]})
        assert result == Decimal("10000")

    def test_unknown_function_raises(self) -> None:
        with pytest.raises(EvaluationError, match="Unknown function"):
            ev({"node": "CALL", "name": "evil", "args": []})


class TestSafety:
    def test_unknown_node_type_raises(self) -> None:
        with pytest.raises(EvaluationError, match="Unknown AST node type"):
            ev({"node": "EXEC", "code": "import os"})

    def test_malformed_node_raises(self) -> None:
        with pytest.raises(EvaluationError):
            ev("not a dict")  # type: ignore[arg-type]

    def test_depth_limit_enforced(self) -> None:
        # Build a deeply nested ADD tree exceeding MAX_DEPTH
        node: dict = {"node": "CONST", "value": 1}
        for _ in range(210):
            node = {"node": "ADD", "args": [node, {"node": "CONST", "value": 0}]}
        with pytest.raises(EvaluationError, match="Maximum recursion depth"):
            ev(node)


class TestTrace:
    def test_trace_records_steps(self) -> None:
        evaluator = Evaluator(variables={"income": 50000}, trace=True)
        evaluator.eval({"node": "VAR", "name": "income"})
        assert len(evaluator.trace_steps) == 1
        assert evaluator.trace_steps[0].node == "VAR"
        assert evaluator.trace_steps[0].output == Decimal("50000")

    def test_no_trace_by_default(self) -> None:
        evaluator = Evaluator(variables={"income": 50000})
        evaluator.eval({"node": "VAR", "name": "income"})
        assert evaluator.trace_steps == []
