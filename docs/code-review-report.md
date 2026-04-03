# Deep Code Review — HMRC Tax MCP (Post-Fix Re-Review)
Re-review date: April 3, 2026

### 1. Summary
The previously identified workflow and validation issues have been addressed. `LET`-backed explanations now work, malformed DSL is normalised into deterministic compile/validation errors, boolean contexts are type-safe, the server module imports cleanly without optional MCP dependencies, NL-extraction drafts now match the registry contract more closely, and stage 5 now auto-loads worked examples with full coverage across the published rule registry. Overall risk level: **low**. The repository is **ready for production use** for the currently implemented rule set.

The current local verification run passed: **`405 passed`**.

### 2. Strengths
- Sequential `LET` evaluation remains correct and deterministic. `src/hmrc_tax_mcp/evaluator.py:88`
- Boolean control flow is now explicit and type-safe; numeric truthiness no longer slips through conditionals. `src/hmrc_tax_mcp/evaluator.py:102`, `src/hmrc_tax_mcp/evaluator.py:168`, `src/hmrc_tax_mcp/evaluator.py:313`
- Canonicalisation still validates both the recompiled AST and the stored AST against the stored checksum. `src/hmrc_tax_mcp/validation/pipeline.py:256`
- `validate_rule()` now auto-loads worked examples by `tax_year` / `jurisdiction` / `rule_id`, so stage 5 is exercised in normal validation flows. `src/hmrc_tax_mcp/validation/pipeline.py:468`
- Worked-example coverage now exists for all published registry rules (`86/86` files present under `tests/worked_examples/`).
- The server module now remains importable without the optional `mcp` dependency, while still failing cleanly at runtime if the transport is unavailable. `src/hmrc_tax_mcp/server.py:15`, `src/hmrc_tax_mcp/server.py:463`
- Extracted draft citations are normalised to the registry schema and draft provenance now uses the expected enum value. `src/hmrc_tax_mcp/extractor/nl_extractor.py:84`, `src/hmrc_tax_mcp/extractor/nl_extractor.py:187`

### 3. Issues Found
No material correctness, safety, or workflow issues remain from the prior review.

### 4. Suggested Refactorings
- Optional: move worked examples from `tests/worked_examples/` into a package-owned data location if you want stage-5 validation to work outside a source checkout.
- Optional: add explicit AST-schema validation on registry load so malformed stored ASTs fail before execution/validation stages.
- Optional: extend example metadata further (`source_label`, `source_url`, `notes`) if you want stronger provenance reporting in validation output.

### 5. Missing or Ambiguous Tax Rules
- Scotland still has no composite `income_tax_due` rule. `docs/rules/known-gaps.md`
- Scottish property-income treatment from 2027-28 onward remains intentionally unimplemented pending Scottish Parliament rate publication. `docs/rules/known-gaps.md`
- The pensioner/state-pension tax guarantee remains a documented policy gap pending legislation. `docs/rules/known-gaps.md`
- If ISA allowance rules are introduced later, the 2027-28 cash-limit split is still only documented as future work. `docs/rules/known-gaps.md`

### 6. Final Recommendation
**Ready for production use** for the implemented rules and current MCP workflow.

Future work should focus on expanding rule coverage rather than further hardening the existing evaluator/validation path.
