# hmrc-tax-mcp

A deterministic, auditable HMRC UK tax rule engine exposed via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

## Purpose

AI agents (Claude, Copilot, Codex) should orchestrate and explain tax strategies — not compute them. This server provides the deterministic calculation layer:

- **LLMs call tools** → this server computes → LLMs explain results
- All rules are versioned, hashed, and cited against HMRC sources
- All arithmetic uses `decimal.Decimal` (no floating-point tax errors)
- Rules are immutable once published; updates create new versions

## Architecture

| Layer | Purpose |
|-------|---------|
| AST | Canonical, sandboxed representation of tax rules |
| DSL | Human-writable language that compiles to AST |
| Evaluator | Safe, `Decimal`-precise AST execution engine |
| Rule Registry | Versioned, hashed, citable rule store |
| Validation Pipeline | 6-stage pipeline incl. HMRC worked examples |
| MCP Server | Stateless tool layer for AI agents (stdio transport) |

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
hmrc-tax-mcp          # starts MCP server on stdio
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `list_rules` | List all rule IDs and versions |
| `get_rule` | Get DSL, AST, metadata for a rule |
| `execute_rule` | Run a rule with inputs → output + optional trace |
| `tax.get_rule_snapshot` | Full rule set for a tax year + jurisdiction |
| `compile_dsl` | Compile DSL text → AST *(coming in Phase 2)* |

## Tax Years Covered

| Year | Jurisdiction | Rules |
|------|-------------|-------|
| 2025–26 | rUK | Income tax bands, personal allowance taper, CGT, UFPLS, pension LSA *(coming in Phase 3)* |

## Design Principles

- **No Turing-complete rules** — no loops, no recursion, no `eval()`
- **Stateless per request** — evaluator is pure with no side effects
- **SHA-256 rule hashing** — canonical JSON for legal reproducibility
- **Human review gate** — required before any rule is published
- **HMRC citations** — every rule entry must reference source URLs

## HMRC Source References

- [Income tax rates](https://www.gov.uk/income-tax-rates)
- [Scottish income tax](https://www.gov.uk/scottish-income-tax)
- [Tax on pensions](https://www.gov.uk/tax-on-pension)
- [Pension scheme rates and allowances](https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates)

## Build Sequence

| Phase | Deliverable |
|-------|------------|
| ✅ 1 | Repo scaffold, AST schema, Evaluator, Registry model, MCP server stub |
| 2 | DSL tokenizer → parser → compiler |
| 3 | 2025–26 rUK rule set (income tax, CGT, PA taper, UFPLS, LSA) |
| 4 | Full validation pipeline (6 stages + worked examples) |
| 5 | NL extractor (LLM-assisted, human-reviewed) |
| 6 | Scottish income tax jurisdiction |
| 7 | Integration with later-life-planner |

## Licence

Private — NxLap Ltd
