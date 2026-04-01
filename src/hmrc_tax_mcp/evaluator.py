"""
Deterministic, sandboxed AST evaluator for HMRC tax rules.

Guarantees:
- Uses decimal.Decimal for all arithmetic (no floating-point errors)
- Rejects unknown or malformed AST nodes
- Enforces a recursion depth limit
- No arbitrary code execution, no eval(), no dynamic imports
- Produces full execution traces for audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from typing import Any

getcontext().prec = 28

MAX_DEPTH = 200


class EvaluationError(Exception):
    """Raised when AST evaluation fails."""


@dataclass
class TraceStep:
    node: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output: Any = None


class Evaluator:
    """
    Walks an AST dict recursively and evaluates it to a Decimal (or bool) result.

    Args:
        variables: Mapping of variable names to numeric values.
        max_depth: Maximum recursion depth (default 200).
        trace: If True, record each evaluation step in self.trace_steps.
    """

    def __init__(
        self,
        variables: dict[str, Any] | None = None,
        max_depth: int = MAX_DEPTH,
        trace: bool = False,
    ) -> None:
        self.vars: dict[str, Any] = variables or {}
        self.max_depth = max_depth
        self.trace = trace
        self.trace_steps: list[TraceStep] = []

    def eval(self, node: dict[str, Any], depth: int = 0) -> Decimal | bool:
        if depth > self.max_depth:
            raise EvaluationError("Maximum recursion depth exceeded")

        if not isinstance(node, dict) or "node" not in node:
            raise EvaluationError(f"Invalid AST node: {node!r}")

        t = node["node"]

        # ------------------------------------------------------------------
        # Primitive nodes
        # ------------------------------------------------------------------
        if t == "CONST":
            val = node["value"]
            if isinstance(val, bool):
                result: Decimal | bool = val
            else:
                result = Decimal(str(val))
            self._record(t, {}, result)
            return result

        if t == "VAR":
            name = node["name"]
            if name not in self.vars:
                raise EvaluationError(f"Unknown variable: {name!r}")
            raw = self.vars[name]
            if isinstance(raw, bool):
                var_result: Decimal | bool = raw
            else:
                var_result = Decimal(str(raw))
            self._record(t, {"name": name}, var_result)
            return var_result

        if t == "LET":
            # Evaluate bindings sequentially so each can reference earlier ones.
            accumulated = dict(self.vars)
            for k, v in node["bindings"].items():
                binding_eval = Evaluator(accumulated, self.max_depth, self.trace)
                accumulated[k] = binding_eval.eval(v, depth + 1)
                self.trace_steps.extend(binding_eval.trace_steps)
            inner = Evaluator(accumulated, self.max_depth, self.trace)
            result = inner.eval(node["body"], depth + 1)
            self.trace_steps.extend(inner.trace_steps)
            self._record(t, {"bindings": list(node["bindings"].keys())}, result)
            return result

        if t == "IF":
            cond = self.eval(node["cond"], depth + 1)
            branch = node["then"] if cond else node["else"]
            result = self.eval(branch, depth + 1)
            self._record(t, {"cond": cond}, result)
            return result

        # ------------------------------------------------------------------
        # Arithmetic
        # ------------------------------------------------------------------
        if t == "ADD":
            args = [self.eval(a, depth + 1) for a in node["args"]]
            dec_args = self._require_decimal_args(args, "ADD")
            result = Decimal(sum(dec_args))
            self._record(t, {"args": args}, result)
            return result

        if t == "SUB":
            args = [self.eval(a, depth + 1) for a in node["args"]]
            dec_args = self._require_decimal_args(args, "SUB")
            if len(dec_args) < 2:
                raise EvaluationError("SUB: requires at least 2 arguments")
            result = dec_args[0] - sum(dec_args[1:])
            self._record(t, {"args": args}, result)
            return result

        if t == "MUL":
            args = [self.eval(a, depth + 1) for a in node["args"]]
            dec_args = self._require_decimal_args(args, "MUL")
            result = Decimal("1")
            for a in dec_args:
                result *= a
            self._record(t, {"args": args}, result)
            return result

        if t == "DIV":
            args = [self.eval(a, depth + 1) for a in node["args"]]
            dec_args = self._require_decimal_args(args, "DIV")
            if len(dec_args) != 2:
                raise EvaluationError("DIV: requires exactly 2 arguments")
            a0, a1 = dec_args
            if a1 == 0:
                raise EvaluationError("Division by zero")
            result = a0 / a1
            self._record(t, {"args": args}, result)
            return result

        # ------------------------------------------------------------------
        # Comparisons
        # ------------------------------------------------------------------
        if t in {"GT", "LT", "GTE", "LTE", "EQ", "NEQ"}:
            a, b = self.eval(node["args"][0], depth + 1), self.eval(node["args"][1], depth + 1)
            bool_result: bool = {
                "GT": lambda x, y: x > y,
                "LT": lambda x, y: x < y,
                "GTE": lambda x, y: x >= y,
                "LTE": lambda x, y: x <= y,
                "EQ": lambda x, y: x == y,
                "NEQ": lambda x, y: x != y,
            }[t](a, b)
            self._record(t, {"a": a, "b": b}, bool_result)
            return bool_result

        # ------------------------------------------------------------------
        # Logical
        # ------------------------------------------------------------------
        if t == "AND":
            bool_result = all(bool(self.eval(a, depth + 1)) for a in node["args"])
            self._record(t, {}, bool_result)
            return bool_result

        if t == "OR":
            bool_result = any(bool(self.eval(a, depth + 1)) for a in node["args"])
            self._record(t, {}, bool_result)
            return bool_result

        if t == "NOT":
            val = self.eval(node["args"][0], depth + 1)
            bool_result = not bool(val)
            self._record(t, {"val": val}, bool_result)
            return bool_result

        # ------------------------------------------------------------------
        # Domain-specific: BAND_APPLY
        # ------------------------------------------------------------------
        if t == "BAND_APPLY":
            income = self.eval(node["args"][0], depth + 1)
            if not isinstance(income, Decimal):
                raise EvaluationError("BAND_APPLY: income must evaluate to a number")
            total = Decimal("0")
            for band in node["bands"]:
                lower = Decimal(str(band["lower"]))
                upper = Decimal(str(band["upper"])) if band.get("upper") is not None else None
                rate = Decimal(str(band["rate"]))
                if income <= lower:
                    continue
                taxable = income - lower
                if upper is not None:
                    taxable = min(taxable, upper - lower)
                if taxable > 0:
                    total += taxable * rate
            self._record(t, {"income": income}, total)
            return total

        # ------------------------------------------------------------------
        # Domain-specific: TAPER
        # ------------------------------------------------------------------
        if t == "TAPER":
            value = self.eval(node["args"][0], depth + 1)
            threshold = self.eval(node["threshold"], depth + 1)
            ratio = self.eval(node["ratio"], depth + 1)
            base = self.eval(node["base"], depth + 1)
            if not isinstance(value, Decimal) or not isinstance(threshold, Decimal):
                raise EvaluationError("TAPER: args must evaluate to numbers")
            if value <= threshold:
                result = base
            else:
                excess = value - threshold
                result = max(base - excess * ratio, Decimal("0"))
            self._record(t, {"value": value, "threshold": threshold}, result)
            return result

        # ------------------------------------------------------------------
        # Domain-specific: CALL
        # ------------------------------------------------------------------
        if t == "CALL":
            fn = node["name"]
            args = [self.eval(a, depth + 1) for a in node["args"]]
            if fn == "percent":
                if not isinstance(args[0], Decimal) or not isinstance(args[1], Decimal):
                    raise EvaluationError("percent(): args must be numbers")
                result = args[0] * (args[1] / Decimal("100"))
                self._record(t, {"fn": fn, "args": args}, result)
                return result
            raise EvaluationError(f"Unknown function: {fn!r}")

        raise EvaluationError(f"Unknown AST node type: {t!r}")

    def _require_decimal_args(self, args: list[Any], op: str) -> list[Decimal]:
        """Validate that all args are Decimal (not bool, str, or None)."""
        result: list[Decimal] = []
        for i, a in enumerate(args):
            if isinstance(a, bool):
                raise EvaluationError(
                    f"{op}: argument {i} is bool; numeric arguments required"
                )
            if not isinstance(a, Decimal):
                raise EvaluationError(
                    f"{op}: argument {i} is {type(a).__name__!r}; numeric arguments required"
                )
            result.append(a)
        return result

    def _record(self, node: str, inputs: dict[str, Any], output: Any) -> None:
        if self.trace:
            self.trace_steps.append(TraceStep(node=node, inputs=inputs, output=output))
