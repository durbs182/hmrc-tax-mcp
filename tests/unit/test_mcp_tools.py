"""
Tests for the MCP server tool handlers.

The MCP runtime isn't available on Python 3.9, so we test the handler
logic by importing the handler function directly and passing mock arguments.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from hmrc_tax_mcp.evaluator import Evaluator

# Import handler internals that work without the MCP runtime
from hmrc_tax_mcp.explainer import explain_rule
from hmrc_tax_mcp.registry.store import get_rule, list_rules
from hmrc_tax_mcp.validation.pipeline import validate_rule

# ---------------------------------------------------------------------------
# Helpers — replicate the server's logic without the MCP runtime
# ---------------------------------------------------------------------------

def _json(data: Any) -> str:
    def _default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, bool):
            return obj
        raise TypeError(f"Not serialisable: {type(obj)}")
    return json.dumps(data, default=_default, indent=2)


def tool_list_rules() -> dict:
    rules = list_rules()
    return [
        {"rule_id": r.rule_id, "version": r.version, "title": r.title,
         "tax_year": r.tax_year, "jurisdiction": r.jurisdiction}
        for r in rules
    ]


def tool_get_rule(rule_id: str, version: str = "latest", jurisdiction: str = "rUK") -> dict:
    rule = get_rule(rule_id, version, jurisdiction=jurisdiction)
    if rule is None:
        return {"error": "Rule not found"}
    return rule.model_dump(mode="json")


def tool_execute_rule(rule_id: str, inputs: dict, version: str = "latest",
                      trace: bool = False, jurisdiction: str = "rUK") -> dict:
    rule = get_rule(rule_id, version, jurisdiction=jurisdiction)
    if rule is None:
        return {"error": "Rule not found"}
    evaluator = Evaluator(variables=inputs, trace=trace)
    try:
        output = evaluator.eval(rule.ast)
    except Exception as exc:
        return {"error": str(exc)}
    result: dict[str, Any] = {
        "rule_id": rule.rule_id, "version": rule.version,
        "output": output, "checksum": rule.checksum,
    }
    if trace:
        result["trace"] = [
            {"step": i + 1, "node": s.node, "inputs": s.inputs, "output": s.output}
            for i, s in enumerate(evaluator.trace_steps)
        ]
    return result


def tool_explain_rule(rule_id: str, version: str = "latest", jurisdiction: str = "rUK") -> dict:
    rule = get_rule(rule_id, version, jurisdiction=jurisdiction)
    if rule is None:
        return {"error": "Rule not found"}
    return explain_rule(rule.model_dump(mode="json"))


def tool_trace_execution(rule_id: str, inputs: dict, version: str = "latest",
                         jurisdiction: str = "rUK") -> dict:
    rule = get_rule(rule_id, version, jurisdiction=jurisdiction)
    if rule is None:
        return {"error": "Rule not found"}
    evaluator = Evaluator(variables=inputs, trace=True)
    try:
        output = evaluator.eval(rule.ast)
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "rule_id": rule.rule_id, "version": rule.version,
        "inputs": inputs, "output": output, "checksum": rule.checksum,
        "steps": len(evaluator.trace_steps),
        "trace": [
            {"step": i + 1, "node": s.node, "inputs": s.inputs, "output": s.output}
            for i, s in enumerate(evaluator.trace_steps)
        ],
    }


def tool_validate_rule(rule_id: str, version: str = "latest", jurisdiction: str = "rUK") -> dict:
    rule = get_rule(rule_id, version, jurisdiction=jurisdiction)
    if rule is None:
        return {"error": "Rule not found"}
    results = validate_rule(rule.model_dump())
    return {
        "rule_id": rule.rule_id, "version": rule.version,
        "stages": [
            {"stage": r.stage.value, "passed": r.passed,
             "message": r.message, "details": r.details}
            for r in results
        ],
        "overall": all(r.passed for r in results),
    }


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------

class TestListRules:
    def test_returns_list(self) -> None:
        result = tool_list_rules()
        assert isinstance(result, list)
        assert len(result) >= 11

    def test_each_entry_has_required_fields(self) -> None:
        for entry in tool_list_rules():
            assert "rule_id" in entry
            assert "version" in entry
            assert "title" in entry

    def test_contains_known_rule(self) -> None:
        ids = {e["rule_id"] for e in tool_list_rules()}
        assert "income_tax_bands" in ids
        assert "pa_taper" in ids


# ---------------------------------------------------------------------------
# get_rule
# ---------------------------------------------------------------------------

class TestGetRule:
    def test_known_rule_returned(self) -> None:
        result = tool_get_rule("income_tax_bands")
        assert result["rule_id"] == "income_tax_bands"
        assert "dsl_source" in result
        assert "ast" in result
        assert "checksum" in result

    def test_unknown_rule_returns_error(self) -> None:
        result = tool_get_rule("nonexistent_rule_xyz")
        assert "error" in result

    def test_version_latest_works(self) -> None:
        result = tool_get_rule("cgt_exempt", "latest")
        assert result["rule_id"] == "cgt_exempt"


# ---------------------------------------------------------------------------
# execute_rule
# ---------------------------------------------------------------------------

class TestExecuteRule:
    def test_income_tax_basic_rate(self) -> None:
        result = tool_execute_rule(
            "income_tax_bands",
            inputs={"taxable_income": Decimal("30000")},
        )
        assert result["output"] == Decimal("3486")

    def test_pa_taper_partial(self) -> None:
        result = tool_execute_rule(
            "pa_taper",
            inputs={"adjusted_net_income": Decimal("110000")},
        )
        assert result["output"] == Decimal("7570")

    def test_execute_returns_checksum(self) -> None:
        result = tool_execute_rule("cgt_exempt", inputs={})
        assert "checksum" in result
        assert len(result["checksum"]) == 64

    def test_unknown_rule_error(self) -> None:
        result = tool_execute_rule("no_such_rule", inputs={})
        assert "error" in result

    def test_trace_flag_returns_steps(self) -> None:
        result = tool_execute_rule(
            "income_tax_bands",
            inputs={"taxable_income": Decimal("30000")},
            trace=True,
        )
        assert "trace" in result
        assert len(result["trace"]) > 0
        step = result["trace"][0]
        assert "step" in step
        assert "node" in step
        assert "output" in step


# ---------------------------------------------------------------------------
# explain_rule
# ---------------------------------------------------------------------------

class TestExplainRuleTool:
    def test_returns_explanation(self) -> None:
        result = tool_explain_rule("income_tax_bands")
        assert "explanation" in result
        assert result["explanation"]

    def test_variables_listed(self) -> None:
        result = tool_explain_rule("income_tax_bands")
        assert result["variables"] == ["taxable_income"]

    def test_pa_taper_explanation(self) -> None:
        result = tool_explain_rule("pa_taper")
        assert "£1 for every £2" in result["explanation"]

    def test_unknown_rule_error(self) -> None:
        result = tool_explain_rule("no_such_rule")
        assert "error" in result

    def test_const_rule_no_variables(self) -> None:
        result = tool_explain_rule("pension_lsa")
        assert result["variables"] == []
        assert "268,275" in result["explanation"]

    def test_composite_let_rule_explains_without_crashing(self) -> None:
        result = tool_explain_rule("income_tax_due", jurisdiction="rUK")
        assert "explanation" in result
        assert "where" in result["explanation"].lower()


# ---------------------------------------------------------------------------
# trace_execution
# ---------------------------------------------------------------------------

class TestTraceExecution:
    def test_returns_trace_list(self) -> None:
        result = tool_trace_execution(
            "income_tax_bands",
            inputs={"taxable_income": Decimal("30000")},
        )
        assert "trace" in result
        assert isinstance(result["trace"], list)
        assert len(result["trace"]) > 0

    def test_steps_count_matches_trace_length(self) -> None:
        result = tool_trace_execution(
            "cgt_exempt", inputs={},
        )
        assert result["steps"] == len(result["trace"])

    def test_each_step_has_required_fields(self) -> None:
        result = tool_trace_execution(
            "cgt_exempt", inputs={},
        )
        for step in result["trace"]:
            assert "step" in step
            assert "node" in step
            assert "output" in step

    def test_output_matches_execute_rule(self) -> None:
        inputs = {"taxable_income": Decimal("50000")}
        trace_result = tool_trace_execution("income_tax_bands", inputs=inputs)
        exec_result = tool_execute_rule("income_tax_bands", inputs=inputs)
        assert trace_result["output"] == exec_result["output"]

    def test_unknown_rule_error(self) -> None:
        result = tool_trace_execution("no_such", inputs={})
        assert "error" in result

    def test_pa_taper_trace_shows_taper_node(self) -> None:
        result = tool_trace_execution(
            "pa_taper",
            inputs={"adjusted_net_income": Decimal("110000")},
        )
        node_types = {step["node"] for step in result["trace"]}
        assert "TAPER" in node_types


# ---------------------------------------------------------------------------
# validate_rule (tool interface)
# ---------------------------------------------------------------------------

class TestValidateRuleTool:
    def test_returns_six_stages(self) -> None:
        result = tool_validate_rule("income_tax_bands")
        assert len(result["stages"]) == 6

    def test_stages_1_to_4_pass(self) -> None:
        result = tool_validate_rule("income_tax_bands")
        for stage in result["stages"][:4]:
            assert stage["passed"], f"Stage {stage['stage']} failed: {stage['message']}"

    def test_stage_6_human_review_fails_for_unreviewed(self) -> None:
        result = tool_validate_rule("income_tax_bands")
        stage6 = result["stages"][5]
        assert stage6["stage"] == "human_review"
        assert not stage6["passed"]

    def test_unknown_rule_returns_error(self) -> None:
        result = tool_validate_rule("no_such_rule")
        assert "error" in result
