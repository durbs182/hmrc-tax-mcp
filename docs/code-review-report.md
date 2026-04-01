# Deep Code Review — HMRC Tax MCP (Re‑Review)
Re-review date: April 1, 2026

### 1. Summary
The previously reported high‑severity issues (LET semantics, arithmetic type safety, band validation, AST/DSL checksum drift, rUK income‑tax input ambiguity, schema drift, missing tests, and rounding policy documentation) have been resolved. The two remaining items from the last review (LET checksum order and rounding policy enforcement) are now fixed via ordered‑binding canonicalisation and monetary‑output validation. Overall risk level: **low**. The code is **production‑ready** from a correctness and safety standpoint, with remaining work largely in feature coverage.

### 2. Strengths
- Sequential `LET` evaluation matches the DSL’s intended semantics. `src/hmrc_tax_mcp/evaluator.py:88-99`.
- Arithmetic nodes enforce numeric inputs and arity; runtime errors are explicit. `src/hmrc_tax_mcp/evaluator.py:111-146`, `src/hmrc_tax_mcp/evaluator.py:266-279`.
- Band validation is enforced at compile time. `src/hmrc_tax_mcp/dsl/compiler.py:31-52`, `src/hmrc_tax_mcp/dsl/compiler.py:167-174`.
- Canonicalisation now validates both DSL‑compiled AST and stored AST against the checksum. `src/hmrc_tax_mcp/validation/pipeline.py:163-212`.
- AST schema and tests cover `NEG`, rounding, sequential `LET`, band validation, and AST/DSL divergence. `src/hmrc_tax_mcp/ast/schema.py`, `tests/unit/test_evaluator.py`, `tests/unit/test_dsl.py`, `tests/unit/test_validation.py`.
- Rounding policy is documented for rule authors. `docs/rules/rounding-policy.md`.

### 3. Issues Found
No material issues found in this re‑review.

### 4. Suggested Refactorings
- Optional: encode `LET` bindings as ordered lists in the AST schema itself (not just canonicalisation) to make order explicit across tooling.
- Optional: extend monetary‑output validation to check that the *final* AST node is a `round()` call, not just that any `round()` exists.

### 5. Missing or Ambiguous Tax Rules
- No composite rule orchestrating PA taper + taxable income derivation + bands.
- Dividend tax rates, NI, student loans, marriage allowance, blind person’s allowance remain unimplemented.
- CGT rate determination is simplified and does not model asset class or remaining basic‑rate band.
- No explicit residency/tax‑year boundary switching logic.

### 6. Final Recommendation
**Ready for production use** with respect to correctness, safety, and auditability. Future work should focus on expanding rule coverage and adding composite rules.
