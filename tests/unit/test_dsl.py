"""Unit tests for the DSL parser and compiler (end-to-end DSL → AST)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl
from hmrc_tax_mcp.evaluator import EvaluationError, Evaluator


def compile_and_eval(dsl: str, vars: dict | None = None) -> Decimal | bool:
    """Compile DSL and evaluate against given variables."""
    ast = compile_dsl(dsl)
    return Evaluator(variables=vars or {}).eval(ast)


class TestSimpleExpressions:
    def test_const(self) -> None:
        assert compile_and_eval("return 12570") == Decimal("12570")

    def test_var(self) -> None:
        assert compile_and_eval("return income", {"income": 50000}) == Decimal("50000")

    def test_add(self) -> None:
        assert compile_and_eval("return 100 + 50") == Decimal("150")

    def test_sub(self) -> None:
        assert compile_and_eval("return income - 12570", {"income": 50000}) == Decimal("37430")

    def test_mul(self) -> None:
        assert compile_and_eval("return 10 * 3") == Decimal("30")

    def test_div(self) -> None:
        assert compile_and_eval("return 100 / 4") == Decimal("25")

    def test_operator_precedence_mul_before_add(self) -> None:
        # 2 + 3 * 4 = 14, not 20
        assert compile_and_eval("return 2 + 3 * 4") == Decimal("14")

    def test_parentheses_override_precedence(self) -> None:
        assert compile_and_eval("return (2 + 3) * 4") == Decimal("20")


class TestLetBindings:
    def test_single_let(self) -> None:
        dsl = "let pa = 12570\nreturn pa"
        assert compile_and_eval(dsl) == Decimal("12570")

    def test_multiple_lets(self) -> None:
        dsl = "let pa = 12570\nlet threshold = 100000\nreturn threshold - pa"
        assert compile_and_eval(dsl) == Decimal("87430")

    def test_let_using_variable(self) -> None:
        dsl = "let taxable = income - 12570\nreturn taxable"
        assert compile_and_eval(dsl, {"income": 50000}) == Decimal("37430")


class TestComparisons:
    def test_gt(self) -> None:
        assert compile_and_eval("return income > 100000", {"income": 110000}) is True

    def test_lte(self) -> None:
        assert compile_and_eval("return income <= 100000", {"income": 100000}) is True

    def test_eq(self) -> None:
        assert compile_and_eval("return income == 12570", {"income": 12570}) is True


class TestLogical:
    def test_and(self) -> None:
        result = compile_and_eval(
            "return income > 0 and income < 100000",
            {"income": 50000},
        )
        assert result is True

    def test_or(self) -> None:
        result = compile_and_eval(
            "return income < 0 or income > 10000",
            {"income": 50000},
        )
        assert result is True

    def test_not(self) -> None:
        result = compile_and_eval("return not (income > 100000)", {"income": 50000})
        assert result is True

    def test_if_condition_must_be_boolean(self) -> None:
        with pytest.raises(EvaluationError, match="IF condition must evaluate to bool"):
            compile_and_eval("return if 2 then 10 else 20")

    def test_and_argument_must_be_boolean(self) -> None:
        with pytest.raises(EvaluationError, match="AND argument 0 must evaluate to bool"):
            compile_and_eval("return 2 and true")

    def test_not_argument_must_be_boolean(self) -> None:
        with pytest.raises(EvaluationError, match="NOT argument must evaluate to bool"):
            compile_and_eval("return not 3")


class TestFunctionCall:
    def test_percent(self) -> None:
        assert compile_and_eval("return percent(50000, 20)") == Decimal("10000")

    def test_unknown_function_raises(self) -> None:
        with pytest.raises(CompileError, match="Unknown function"):
            compile_dsl("return evil(1, 2)")


class TestBands:
    INCOME_TAX_DSL = """\
bands taxable_income:
  0 to 37700 at 20%
  37700 to 125140 at 40%
  125140+ at 45%
"""

    def test_basic_rate(self) -> None:
        result = compile_and_eval(self.INCOME_TAX_DSL, {"taxable_income": 20000})
        assert result == Decimal("4000")

    def test_higher_rate_boundary(self) -> None:
        # £40,000: 20%×37700 + 40%×2300 = £7,540 + £920 = £8,460
        result = compile_and_eval(self.INCOME_TAX_DSL, {"taxable_income": 40000})
        assert result == Decimal("8460")

    def test_nil_income(self) -> None:
        result = compile_and_eval(self.INCOME_TAX_DSL, {"taxable_income": 0})
        assert result == Decimal("0")

    def test_additional_rate(self) -> None:
        # £130,000: 20%×37700 + 40%×87440 + 45%×4860 = 7540+34976+2187 = 44703
        result = compile_and_eval(self.INCOME_TAX_DSL, {"taxable_income": 130000})
        assert result == Decimal("44703")

    def test_compile_produces_band_apply_node(self) -> None:
        ast = compile_dsl(self.INCOME_TAX_DSL)
        assert ast["node"] == "BAND_APPLY"
        assert len(ast["bands"]) == 3
        assert ast["bands"][2]["upper"] is None  # open-ended top band

    def test_bands_without_percent_sign(self) -> None:
        dsl = "bands income:\n  0 to 37700 at 20\n  37700+ at 40\n"
        result = compile_and_eval(dsl, {"income": 20000})
        assert result == Decimal("4000")


class TestTaper:
    TAPER_DSL = """\
taper adjusted_net_income:
  threshold 100000
  ratio 1 per 2
  base 12570
"""

    def test_below_threshold(self) -> None:
        assert compile_and_eval(self.TAPER_DSL, {"adjusted_net_income": 80000}) == Decimal("12570")

    def test_partially_tapered(self) -> None:
        # £110,000 → excess £10,000 → reduction £5,000 → allowance £7,570
        assert compile_and_eval(self.TAPER_DSL, {"adjusted_net_income": 110000}) == Decimal("7570")

    def test_fully_tapered(self) -> None:
        assert compile_and_eval(self.TAPER_DSL, {"adjusted_net_income": 125140}) == Decimal("0")

    def test_compile_produces_taper_node(self) -> None:
        ast = compile_dsl(self.TAPER_DSL)
        assert ast["node"] == "TAPER"
        assert ast["threshold"]["value"] == 100000
        assert ast["ratio"]["value"] == pytest.approx(0.5)
        assert ast["base"]["value"] == 12570


class TestBoolLiterals:
    def test_true(self) -> None:
        result = compile_and_eval("return true")
        assert result is True

    def test_false_in_condition(self) -> None:
        ast = compile_dsl("return false")
        assert ast == {"node": "CONST", "value": False}


class TestParseErrors:
    def test_empty_source_raises(self) -> None:
        with pytest.raises(CompileError, match="empty"):
            compile_dsl("")

    def test_missing_return_raises(self) -> None:
        with pytest.raises((CompileError, Exception)):
            compile_dsl("let x = 1")

    def test_empty_bands_raises(self) -> None:
        with pytest.raises(CompileError, match="Expected NEWLINE, got EOF"):
            compile_dsl("bands income:\n")

    def test_taper_zero_denominator_raises_compile_error(self) -> None:
        dsl = """\
taper adjusted_net_income:
  threshold 100000
  ratio 1 per 0
  base 12570
"""
        with pytest.raises(CompileError, match="denominator must be non-zero"):
            compile_dsl(dsl)


class TestRoundtrip:
    """Compile DSL → AST → evaluate and verify against known HMRC values."""

    def test_pa_taper_hmrc_example(self) -> None:
        """HMRC example: income £110,000 → tapered PA = £7,570."""
        dsl = """\
taper adjusted_net_income:
  threshold 100000
  ratio 1 per 2
  base 12570
"""
        assert compile_and_eval(dsl, {"adjusted_net_income": 110000}) == Decimal("7570")

    def test_income_tax_hmrc_example(self) -> None:
        """Basic-rate taxpayer with £30,000 taxable income → £6,000 tax."""
        dsl = """\
bands taxable_income:
  0 to 37700 at 20%
  37700 to 125140 at 40%
  125140+ at 45%
"""
        assert compile_and_eval(dsl, {"taxable_income": 30000}) == Decimal("6000")


# ---------------------------------------------------------------------------
# Band validation error tests — issue 3
# ---------------------------------------------------------------------------

class TestBandValidationErrors:
    """Compiler must reject semantically invalid band definitions."""

    def test_overlapping_bands_rejected(self) -> None:
        from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl
        dsl = """\
bands income:
  0 to 50000 at 20%
  30000 to 100000 at 40%
  100000+ at 45%
"""
        with pytest.raises(CompileError, match="contiguous and non-overlapping"):
            compile_dsl(dsl)

    def test_gap_between_bands_rejected(self) -> None:
        from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl
        dsl = """\
bands income:
  0 to 20000 at 20%
  30000 to 100000 at 40%
  100000+ at 45%
"""
        with pytest.raises(CompileError, match="contiguous and non-overlapping"):
            compile_dsl(dsl)

    def test_inverted_band_upper_lower_rejected(self) -> None:
        from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl
        dsl = """\
bands income:
  50000 to 0 at 20%
  0+ at 40%
"""
        with pytest.raises(CompileError, match="greater than lower"):
            compile_dsl(dsl)

    def test_band_after_open_ended_rejected(self) -> None:
        """A band following an open-ended (upper=null) band must be rejected."""
        from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl
        dsl = """\
bands income:
  0 to 50000 at 20%
  50000+ at 40%
  100000 to 150000 at 45%
"""
        with pytest.raises(CompileError, match="cannot follow an open-ended band"):
            compile_dsl(dsl)
