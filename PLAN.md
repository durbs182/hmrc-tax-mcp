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

### Phase 2 — DSL + Parser + Compiler
- [ ] `dsl-tokenizer` — Regex tokenizer: IDENT, NUMBER, OP, KEYWORD, PUNCT
- [ ] `dsl-parser` — Recursive-descent parser implementing EBNF grammar
- [ ] `dsl-compiler` — Parse tree → canonical AST; unit tests for all node types

### Phase 3 — Rule Registry & 2025–26 rUK Rule Set
- [ ] `rule-registry` — Verified YAML store, load/lookup, get_rule_snapshot
- [ ] `first-ruleset` — Income tax bands, PA taper, CGT, UFPLS, LSA — HMRC citations required

### Phase 4 — Validation Pipeline
- [ ] `validation-pipeline` — 6 stages: syntax → semantic → canonicalisation → execution → worked examples → human review gate

### Phase 5 — MCP Server (full)
- [ ] `mcp-server` — All tools wired: list_rules, get_rule, execute_rule, explain_rule, validate_rule, compile_dsl, trace_execution, tax.get_rule_snapshot

### Phase 6 — NL Extractor
- [ ] `nl-extractor` — LLM (Anthropic Claude) → DSL with mandatory human review gate

### Phase 7 — Scottish Income Tax
- [ ] `scotland-rules` — Scottish income tax bands 2025–26; jurisdiction field support

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
| `list_rules` | ✅ stub | List all rule IDs and versions |
| `get_rule` | ✅ stub | DSL, AST, metadata for a rule |
| `execute_rule` | ✅ working | Run rule with inputs → output + trace |
| `tax.get_rule_snapshot` | ✅ stub | Full rule set for tax year + jurisdiction |
| `compile_dsl` | ⏳ Phase 2 | DSL text → AST |
| `explain_rule` | ⏳ Phase 5 | Human-readable rule explanation |
| `validate_rule` | ⏳ Phase 4 | Full 6-stage validation pipeline |
| `trace_execution` | ⏳ Phase 5 | Full execution trace for audit |

---

## 2025–26 rUK Rule Set (Phase 3 target)

| Rule ID | Description | HMRC Source |
|---------|-------------|-------------|
| `income_tax.bands.2025-26.ruk` | Basic/higher/additional rate bands | https://www.gov.uk/income-tax-rates |
| `income_tax.pa_taper.2025-26.ruk` | Personal allowance taper (£100k threshold) | https://www.gov.uk/income-tax-rates |
| `cgt.exempt.2025-26.ruk` | CGT annual exempt amount (£3,000) | https://www.gov.uk/capital-gains-tax/allowances |
| `cgt.rates.2025-26.ruk` | CGT rates (residential / other) | https://www.gov.uk/capital-gains-tax/rates |
| `pension.ufpls.2025-26` | UFPLS 25% tax-free / 75% taxable | https://www.gov.uk/tax-on-pension |
| `pension.lsa.2025-26` | Lump Sum Allowance £268,275 | https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates |
| `income_tax.state_pension.2025-26` | New State Pension full rate | https://www.gov.uk/new-state-pension/what-youll-get |

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
