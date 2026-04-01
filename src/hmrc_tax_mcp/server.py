"""
HMRC Tax MCP Server — stdio transport.

Exposes deterministic HMRC tax rule tools to AI agents via the Model Context Protocol.
LLMs orchestrate and explain; this server computes.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

from hmrc_tax_mcp.ast.canonical import ast_checksum
from hmrc_tax_mcp.dsl.compiler import CompileError, compile_dsl as _compile_dsl
from hmrc_tax_mcp.evaluator import Evaluator, EvaluationError
from hmrc_tax_mcp.registry.store import get_rule, get_rule_snapshot, list_rules

app = Server("hmrc-tax-mcp") if _MCP_AVAILABLE else None  # type: ignore[assignment]


def _json(data: Any) -> str:
    def _default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

    return json.dumps(data, default=_default, indent=2)


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_rules",
            description="List all available HMRC tax rule IDs and versions.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_rule",
            description="Get DSL source, AST, and metadata for a specific rule.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "e.g. 'pa.taper.2025-26'"},
                    "version": {"type": "string", "description": "Semver or 'latest'", "default": "latest"},
                },
                "required": ["rule_id"],
            },
        ),
        Tool(
            name="execute_rule",
            description=(
                "Execute a tax rule with given inputs and return the result. "
                "All arithmetic uses decimal.Decimal for precision."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "version": {"type": "string", "default": "latest"},
                    "inputs": {
                        "type": "object",
                        "description": "Variable bindings for the rule, e.g. {'adjusted_net_income': 110000}",
                    },
                    "trace": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, include a full execution trace in the response.",
                    },
                },
                "required": ["rule_id", "inputs"],
            },
        ),
        Tool(
            name="tax.get_rule_snapshot",
            description="Return the complete rule set for a given tax year and jurisdiction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tax_year": {"type": "string", "description": "e.g. '2025-26'"},
                    "jurisdiction": {"type": "string", "description": "'rUK' or 'scotland'"},
                },
                "required": ["tax_year", "jurisdiction"],
            },
        ),
        Tool(
            name="compile_dsl",
            description="Compile DSL text to a canonical AST, returning the AST and its SHA-256 checksum.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dsl": {"type": "string", "description": "DSL source text"},
                },
                "required": ["dsl"],
            },
        ),
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "list_rules":
        rules = list_rules()
        data = [
            {
                "rule_id": r.rule_id,
                "version": r.version,
                "title": r.title,
                "tax_year": r.tax_year,
                "jurisdiction": r.jurisdiction,
            }
            for r in rules
        ]
        return [TextContent(type="text", text=_json(data))]

    if name == "get_rule":
        rule = get_rule(arguments["rule_id"], arguments.get("version", "latest"))
        if rule is None:
            return [TextContent(type="text", text=_json({"error": "Rule not found"}))]
        return [TextContent(type="text", text=_json(rule.model_dump(mode="json")))]

    if name == "execute_rule":
        rule = get_rule(arguments["rule_id"], arguments.get("version", "latest"))
        if rule is None:
            return [TextContent(type="text", text=_json({"error": "Rule not found"}))]
        evaluator = Evaluator(
            variables=arguments.get("inputs", {}),
            trace=arguments.get("trace", False),
        )
        try:
            output = evaluator.eval(rule.ast)
        except EvaluationError as exc:
            return [TextContent(type="text", text=_json({"error": str(exc)}))]

        response: dict[str, Any] = {
            "rule_id": rule.rule_id,
            "version": rule.version,
            "output": output,
            "checksum": rule.checksum,
        }
        if arguments.get("trace"):
            response["trace"] = [
                {"node": s.node, "inputs": s.inputs, "output": s.output}
                for s in evaluator.trace_steps
            ]
        return [TextContent(type="text", text=_json(response))]

    if name == "tax.get_rule_snapshot":
        rules = get_rule_snapshot(arguments["tax_year"], arguments["jurisdiction"])
        data = {
            "tax_year": arguments["tax_year"],
            "jurisdiction": arguments["jurisdiction"],
            "rules": [r.model_dump(mode="json") for r in rules],
        }
        return [TextContent(type="text", text=_json(data))]

    if name == "compile_dsl":
        dsl_src = arguments.get("dsl", "")
        try:
            ast_node = _compile_dsl(dsl_src)
            checksum = ast_checksum(ast_node)
            return [TextContent(type="text", text=_json({"ast": ast_node, "checksum": checksum}))]
        except CompileError as exc:
            return [TextContent(type="text", text=_json({"error": str(exc)}))]

    return [TextContent(type="text", text=_json({"error": f"Unknown tool: {name!r}"}))]


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "MCP server requires Python >=3.10. "
            "Install with: pip install 'hmrc-tax-mcp[server]'"
        )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
