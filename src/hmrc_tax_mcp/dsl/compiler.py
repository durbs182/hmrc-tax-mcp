"""
DSL → AST compiler.

Walks the parse tree produced by parser.parse() and emits canonical AST
node dicts. The compiler's output is ready for the Evaluator and for
storage in the rule registry.

The compiler handles two forms:
  - Single-expression DSL (a bare expr with no let/return)
  - Multi-statement DSL with let bindings and a final return

Multi-statement programs compile to a nested LET node:
  let a = 1
  let b = 2
  return a + b

→ {"node": "LET", "bindings": {"a": CONST(1), "b": CONST(2)}, "body": ADD(VAR(a), VAR(b))}
"""

from __future__ import annotations

from typing import Any

from hmrc_tax_mcp.dsl.parser import parse


class CompileError(Exception):
    pass


def _validate_bands(bands: list[dict[str, Any]]) -> None:
    """
    Validate that bands are strictly monotonic: each band's lower must equal
    the prior band's upper, and upper (if present) must be > lower.
    """
    from decimal import Decimal as _D

    prev_upper: _D | None = None
    for i, band in enumerate(bands):
        lower = _D(str(band["lower"]))
        upper = _D(str(band["upper"])) if band.get("upper") is not None else None
        if upper is not None and upper <= lower:
            raise CompileError(
                f"Band {i}: upper ({upper}) must be greater than lower ({lower})"
            )
        if prev_upper is not None and lower != prev_upper:
            raise CompileError(
                f"Band {i}: lower ({lower}) must equal the prior band's upper ({prev_upper}); "
                "bands must be contiguous and non-overlapping"
            )
        prev_upper = upper


def compile_dsl(dsl_text: str) -> dict[str, Any]:
    """
    Compile DSL source text to a canonical AST dict.

    Args:
        dsl_text: Raw DSL source.

    Returns:
        Canonical AST dict ready for the Evaluator or registry storage.

    Raises:
        CompileError: On semantic errors.
        ParseError: On syntax errors.
        TokenizeError: On tokenizer errors.
    """
    stmts = parse(dsl_text.strip())

    if not stmts:
        raise CompileError("DSL source is empty")

    # Separate let bindings from the final expression/return
    bindings: dict[str, Any] = {}
    body: dict[str, Any] | None = None

    for stmt in stmts:
        kind = stmt["stmt"]
        if kind == "let":
            name = stmt["name"]
            if name in bindings:
                raise CompileError(f"Duplicate let binding: {name!r}")
            bindings[name] = _compile_expr(stmt["expr"])
        elif kind == "return":
            if body is not None:
                raise CompileError("Multiple return statements are not allowed")
            body = _compile_expr(stmt["expr"])
        elif kind == "expr":
            # A bare expression statement — treat as the body if there's only one
            if body is not None:
                raise CompileError("Multiple expression statements are not allowed")
            body = _compile_expr(stmt["expr"])
        else:
            raise CompileError(f"Unknown statement kind: {kind!r}")

    if body is None:
        raise CompileError("DSL must have a final return or expression")

    if bindings:
        return {"node": "LET", "bindings": bindings, "body": body}
    return body


def _compile_expr(expr: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively compile a parse-tree expression dict to a canonical AST dict.

    The parse tree from parser.py already uses canonical node keys for most
    nodes (CONST, VAR, ADD, SUB, etc.), so for most nodes this is a
    structural pass with recursive child compilation.
    """
    node = expr.get("node")
    if node is None:
        raise CompileError(f"Missing 'node' key in expression: {expr!r}")

    # Leaf nodes
    if node in ("CONST", "VAR"):
        return dict(expr)

    # Arithmetic / logical / comparison nodes with "args" list
    if node in ("ADD", "SUB", "MUL", "DIV",
                "GT", "LT", "GTE", "LTE", "EQ", "NEQ",
                "AND", "OR", "NOT"):
        return {
            "node": node,
            "args": [_compile_expr(a) for a in expr["args"]],
        }

    # CALL
    if node == "CALL":
        _allowed_fns = {"percent"}
        if expr["name"] not in _allowed_fns:
            raise CompileError(
                f"Unknown function {expr['name']!r}. Allowed: {sorted(_allowed_fns)}"
            )
        return {
            "node": "CALL",
            "name": expr["name"],
            "args": [_compile_expr(a) for a in expr["args"]],
        }

    # IF
    if node == "IF":
        return {
            "node": "IF",
            "cond": _compile_expr(expr["args"][0]),
            "then": _compile_expr(expr["args"][1]),
            "else": _compile_expr(expr["args"][2]),
        }

    # LET (nested)
    if node == "LET":
        return {
            "node": "LET",
            "bindings": {k: _compile_expr(v) for k, v in expr["bindings"].items()},
            "body": _compile_expr(expr["body"]),
        }

    # BAND_APPLY — parser already builds the bands list correctly
    if node == "BAND_APPLY":
        _validate_bands(expr["bands"])
        return {
            "node": "BAND_APPLY",
            "args": [_compile_expr(a) for a in expr["args"]],
            "bands": expr["bands"],  # [{"lower": N, "upper": N|null, "rate": F}]
        }

    # TAPER — parser already builds threshold/ratio/base as CONST nodes
    if node == "TAPER":
        return {
            "node": "TAPER",
            "args": [_compile_expr(a) for a in expr["args"]],
            "threshold": _compile_expr(expr["threshold"]),
            "ratio": _compile_expr(expr["ratio"]),
            "base": _compile_expr(expr["base"]),
        }

    raise CompileError(f"Unknown AST node type in parse tree: {node!r}")
