# PLAN.md — hmrc-tax-mcp

Deterministic HMRC UK tax rule engine exposed via the Model Context Protocol.  
Owner: NxLap Ltd | Repo: `durbs182/hmrc-tax-mcp` (private)

---

## Problem Statement

AI agents (Claude, Copilot, Codex) should orchestrate and explain UK tax strategies — not compute them. This server provides the deterministic calculation layer:

- LLMs call MCP tools → this server computes → LLMs explain results
- All rules are versioned, hashed, and cited against HMRC sources
- All arithmetic uses `decimal.Decimal` (no floating-point tax errors)
- Rules are immutable once published; updates create new versions

---

## Architecture

| Layer | Module | Purpose |
|-------|--------|---------|
| AST | `ast/schema.py`, `ast/canonical.py` | Canonical, sandboxed rule representation + SHA-256 hashing |
| Evaluator | `evaluator.py` | Safe, Decimal-precise AST execution engine |
| DSL | `dsl/tokenizer.py`, `dsl/parser.py`, `dsl/compiler.py` | Human-writable rule language → AST |
| Rule Registry | `registry/model.py`, `registry/store.py`, `registry/rules/` | Versioned, hashed, citable rule store |
| Validation Pipeline | `validation/pipeline.py` | 6-stage pipeline incl. HMRC worked examples |
| MCP Server | `server.py` | Stateless tool layer for AI agents (stdio transport) |
| NL Extractor | `extractor/nl_extractor.py` | LLM-assisted HMRC prose → DSL (human-reviewed) |

---

## Build Checklist

### Phase 1 — Repo Scaffold & Core AST/Evaluator ✅
- [x] `repo-scaffold` — GitHub repo, pyproject.toml, src layout, CI workflow
- [x] `ast-schema` — AST node types (Pydantic), JSON schema, forward-ref rebuild
- [x] `evaluator` — Decimal-precise evaluator, depth limit, trace, 52 unit tests

### Phase 2 — DSL + Parser + Compiler ✅
- [x] `dsl-tokenizer` — Regex tokenizer: IDENT, NUMBER, OP, KEYWORD, PUNCT, NEWLINE
- [x] `dsl-parser` — Recursive-descent parser: let, return, if/then/else, bands, taper
- [x] `dsl-compiler` — Parse tree → canonical AST; 50 unit tests

### Phase 3 — Rule Registry & 2025–26 rUK Rule Set ✅
- [x] `rule-registry` — YAML store, lazy loading, get_rule(), list_rules(), get_rule_snapshot()
- [x] `first-ruleset` — 11 rules: income_tax_bands, pa_taper, cgt_exempt, cgt_rates, pension_ufpls_tax_free_fraction, pension_ufpls_taxable_fraction, pension_lsa, state_pension_annual, savings_allowance_basic, savings_allowance_higher, dividend_allowance

### Phase 4 — Validation Pipeline ✅
- [x] `validation-pipeline` — 6 stages: syntax → semantic → canonicalisation → execution → worked examples → human review gate
- [x] Worked example YAML files for all 11 rUK 2025–26 rules
- [x] `validate_rule` MCP tool wired into server.py
- [x] 30 pipeline unit tests; 143 total tests passing

### Phase 5 — MCP Server (full) ✅
- [x] `mcp-server` — `explain_rule` tool: AST walker → human-readable prose + variable list + citations
- [x] `mcp-server` — `trace_execution` tool: full step-by-step audit trace with node-level inputs/outputs
- [x] `explainer.py` — deterministic AST → prose; comma-formatted numbers; coverage for CONST, BAND_APPLY, TAPER, IF, arithmetic nodes
- [x] 46 new tests (test_explainer.py + test_mcp_tools.py); **189 total tests passing**

### Phase 6 — NL Extractor ✅
- [x] `nl-extractor` — `NLExtractor` class: HMRC prose → draft DSL via Anthropic Claude
- [x] `ExtractionResult` dataclass: `reviewed_by`, `requires_review`, `to_registry_dict()`, `warnings`
- [x] `_parse_response()`: JSON delimiter (`<<<JSON / JSON>>>`), markdown fence stripping, fallback handling
- [x] `extract_rule` MCP tool wired into server.py — returns draft, checksum, compile error, review gate
- [x] All output permanently tagged `reviewed_by: null` — mandatory human review before publication
- [x] 32 new tests (all mocked — no real API calls); **221 total tests passing**

### Phase 7 — Scottish Income Tax ✅
- [x] `scotland-rules` — 6 Scotland YAML rules: income_tax_bands (6-band: starter/basic/intermediate/higher/advanced/top), pa_taper, savings_allowance_starter, savings_allowance_basic, savings_allowance_higher, dividend_allowance
- [x] Registry key updated to `{rule_id}@{version}@{jurisdiction}` — supports same rule_id across jurisdictions
- [x] `get_rule()` gains optional `jurisdiction` parameter for disambiguation
- [x] Worked examples for Scotland income_tax_bands (7 cases) and pa_taper (5 cases)
- [x] 33 new tests (`test_scotland_rules.py`); **254 total tests passing**

### Phase 8 — Integration
- [ ] `integration-docs` — Integration guide: how later-life-planner calls the MCP tools

---

## DSL Syntax Reference

```
# Arithmetic
return income - 12570

# Bands (compiles to BAND_APPLY)
bands taxable_income:
  0 to 37700 at 20%
  37700 to 125140 at 40%
  125140+ at 45%

# Taper (compiles to TAPER)
taper adjusted_net_income:
  threshold 100000
  ratio 1 per 2
  base 12570

# LET bindings
let pa = 12570
let threshold = 100000
return pa - threshold

# Function call
percent(50000, 20)
```

---

## MCP Tools

| Tool | Status | Purpose |
|------|--------|---------|
| `list_rules` | ✅ live | List all rule IDs and versions |
| `get_rule` | ✅ live | DSL, AST, metadata for a rule |
| `execute_rule` | ✅ live | Run rule with inputs → output + trace |
| `tax.get_rule_snapshot` | ✅ live | Full rule set for tax year + jurisdiction |
| `compile_dsl` | ✅ live | DSL text → AST + SHA-256 checksum |
| `validate_rule` | ✅ live | Full 6-stage validation pipeline |
| `explain_rule` | ⏳ Phase 5 | Human-readable rule explanation |
| `trace_execution` | ⏳ Phase 5 | Full execution trace for audit |

---

## 2025–26 rUK Rule Set ✅

| Rule ID | Description | HMRC Source |
|---------|-------------|-------------|
| `income_tax_bands` | Basic/higher/additional rate bands + nil band | [Income tax rates](https://www.gov.uk/income-tax-rates) |
| `pa_taper` | Personal allowance taper (£100k threshold, £12,570 base) | [Income tax rates](https://www.gov.uk/income-tax-rates) |
| `cgt_exempt` | CGT annual exempt amount (£3,000) | [CGT allowances](https://www.gov.uk/capital-gains-tax/allowances) |
| `cgt_rates` | CGT rates: 24% higher, 18% basic | [CGT rates](https://www.gov.uk/capital-gains-tax/rates) |
| `pension_ufpls_tax_free_fraction` | UFPLS tax-free fraction (0.25) | [Tax on pension](https://www.gov.uk/tax-on-pension) |
| `pension_ufpls_taxable_fraction` | UFPLS taxable fraction (0.75) | [Tax on pension](https://www.gov.uk/tax-on-pension) |
| `pension_lsa` | Lump Sum Allowance £268,275 | [Pension scheme rates](https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates) |
| `state_pension_annual` | Full new state pension £11,502.40/year | [New State Pension](https://www.gov.uk/new-state-pension) |
| `savings_allowance_basic` | PSA basic rate £1,000 | [Tax on savings](https://www.gov.uk/apply-tax-free-interest-on-savings) |
| `savings_allowance_higher` | PSA higher rate £500 | [Tax on savings](https://www.gov.uk/apply-tax-free-interest-on-savings) |
| `dividend_allowance` | Dividend allowance £500 | [Tax on dividends](https://www.gov.uk/tax-on-dividends) |

---

## Design Principles

- **No Turing-complete rules** — no loops, no recursion, no `eval()`
- **Stateless per request** — evaluator is pure with no side effects
- **SHA-256 rule hashing** — canonical JSON for legal reproducibility
- **Human review gate** — required before any rule is published
- **HMRC citations required** — every rule entry must reference source URLs
- **MCP transport** — stdio (local); HTTP SSE can be added later

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Language | Python | All mcp.md spec code is Python; Decimal precision |
| Transport | stdio | Simplest to start; SSE for cloud later |
| Python version | >=3.9 (dev), 3.11 (CI) | System constraint; mcp package needs 3.10+ |
| Packaging | git-dep initially | PyPI when stable |
| LLM for NL extractor | Anthropic Claude | Already used in later-life-planner |
