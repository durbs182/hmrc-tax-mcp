"""
Rule explainer: walks a compiled AST and produces structured human-readable
prose describing what a tax rule computes. No LLM required — purely
deterministic from the AST structure.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _fmt(value: Any) -> str:
    """Format a number as a clean string (strip trailing zeros, comma-separate integers)."""
    if isinstance(value, bool):
        return str(value).lower()
    try:
        d = Decimal(str(value))
        normalised = d.normalize()
        s = str(normalised)
        if "E" in s or "." not in s:
            # Whole number — format with commas
            return f"{int(d):,}"
        # Has decimal places — strip trailing zeros
        s = s.rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(value)


def _pct(rate: float) -> str:
    pct = Decimal(str(rate)) * 100
    s = str(pct.normalize())
    if "E" in s:
        s = str(int(pct))
    return f"{s}%"


def _explain_node(node: dict[str, Any], depth: int = 0) -> str:
    """Recursively produce a plain-English description of an AST node."""
    t = node.get("node", "")
    indent = "  " * depth

    if t == "CONST":
        return _fmt(node["value"])

    if t == "VAR":
        return str(node["name"]).replace("_", " ")

    if t == "ADD":
        a, b = node["args"]
        return f"({_explain_node(a, depth)} + {_explain_node(b, depth)})"

    if t == "SUB":
        a, b = node["args"]
        return f"({_explain_node(a, depth)} − {_explain_node(b, depth)})"

    if t == "MUL":
        a, b = node["args"]
        return f"({_explain_node(a, depth)} × {_explain_node(b, depth)})"

    if t == "DIV":
        a, b = node["args"]
        return f"({_explain_node(a, depth)} ÷ {_explain_node(b, depth)})"

    if t == "GT":
        a, b = node["args"]
        return f"{_explain_node(a)} > {_explain_node(b)}"

    if t == "LT":
        a, b = node["args"]
        return f"{_explain_node(a)} < {_explain_node(b)}"

    if t == "GTE":
        a, b = node["args"]
        return f"{_explain_node(a)} ≥ {_explain_node(b)}"

    if t == "LTE":
        a, b = node["args"]
        return f"{_explain_node(a)} ≤ {_explain_node(b)}"

    if t == "EQ":
        a, b = node["args"]
        return f"{_explain_node(a)} = {_explain_node(b)}"

    if t == "NEQ":
        a, b = node["args"]
        return f"{_explain_node(a)} ≠ {_explain_node(b)}"

    if t == "AND":
        a, b = node["args"]
        return f"({_explain_node(a)} and {_explain_node(b)})"

    if t == "OR":
        a, b = node["args"]
        return f"({_explain_node(a)} or {_explain_node(b)})"

    if t == "NOT":
        return f"not {_explain_node(node['args'][0])}"

    if t == "IF":
        cond = _explain_node(node["cond"])
        then = _explain_node(node["then"])
        else_ = _explain_node(node["else"])
        return f"if {cond} then {then}, otherwise {else_}"

    if t == "LET":
        bindings = node.get("bindings", {})
        body = _explain_node(node["body"], depth)
        if not bindings:
            return body
        parts = [f"{k} = {_explain_node(v)}" for k, v in bindings.items()]
        return f"where {', '.join(parts)}: {body}"

    if t == "BAND_APPLY":
        var = _explain_node(node["args"][0])
        bands = node.get("bands", [])
        lines = [f"Progressive tax on {var}:"]
        for b in bands:
            lower = _fmt(b["lower"])
            rate = _pct(b["rate"])
            if b["upper"] is None:
                lines.append(f"  {indent}  above £{lower}: {rate}")
            else:
                upper = _fmt(b["upper"])
                lines.append(f"  {indent}  £{lower} – £{upper}: {rate}")
        return "\n".join(lines)

    if t == "TAPER":
        var = _explain_node(node["args"][0])
        threshold = _explain_node(node["threshold"])
        ratio = node["ratio"]
        base = _explain_node(node["base"])
        # ratio is a CONST node with value = reduction per £1 excess
        ratio_val = ratio.get("value", ratio) if isinstance(ratio, dict) else ratio
        try:
            ratio_d = Decimal(str(ratio_val))
            # e.g. 0.5 → "£1 for every £2"
            denom = int(1 / ratio_d)
            ratio_str = f"£1 for every £{denom}"
        except Exception:
            ratio_str = _explain_node(ratio)
        return (
            f"Taper of {base} base value: reduced by {ratio_str} of {var} above £{threshold}"
        )

    if t == "CALL":
        fn = node["name"]
        args = [_explain_node(a) for a in node.get("args", [])]
        return f"{fn}({', '.join(args)})"

    return f"[{t}]"


def explain_rule(rule_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Produce a structured, human-readable explanation of a tax rule.

    Returns a dict with:
      - title, description, tax_year, jurisdiction
      - dsl_source (the authoritative rule text)
      - explanation (plain-English summary of what the AST computes)
      - variables (list of input variables the rule requires)
      - citations (list of HMRC source references)
      - checksum (SHA-256 of the canonical AST)
    """
    ast = rule_dict.get("ast", {})
    explanation = _explain_node(ast) if isinstance(ast, dict) else "(no AST)"
    variables = _collect_variables(ast)

    return {
        "title": rule_dict.get("title", ""),
        "description": rule_dict.get("description", "").strip(),
        "tax_year": rule_dict.get("tax_year", ""),
        "jurisdiction": rule_dict.get("jurisdiction", ""),
        "dsl_source": rule_dict.get("dsl_source", "").strip(),
        "explanation": explanation,
        "variables": sorted(variables),
        "citations": rule_dict.get("citations", []),
        "checksum": rule_dict.get("checksum", ""),
        "version": rule_dict.get("version", ""),
        "provenance": rule_dict.get("provenance", ""),
    }


def _collect_variables(node: Any) -> set[str]:
    """Walk the AST and collect all VAR node names."""
    variables: set[str] = set()

    def _walk(n: Any) -> None:
        if not isinstance(n, dict):
            return
        if n.get("node") == "VAR":
            variables.add(n["name"])
        for v in n.values():
            if isinstance(v, dict):
                _walk(v)
            elif isinstance(v, list):
                for item in v:
                    _walk(item)

    _walk(node)
    return variables
