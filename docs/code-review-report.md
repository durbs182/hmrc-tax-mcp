# Deep Code Review — HMRC Tax MCP (Re‑Review)

### 1. Summary
The previously reported high‑severity issues around `LET` semantics, arithmetic type safety, band validation, DSL/AST checksum drift, and rUK income‑tax input ambiguity appear to be addressed. The evaluator now enforces numeric types, validates arity, supports unary negation and rounding, and the registry + validation pipeline are stricter. Remaining risks are narrower and mostly in **schema drift** and **test coverage**. Overall risk level: **medium**. The code is **closer to production‑ready**, but still needs a few targeted fixes and tests.

### 2. Strengths
- `LET` bindings now evaluate sequentially, matching the DSL’s intended semantics. `src/hmrc_tax_mcp/evaluator.py:88-99`.
- Arithmetic nodes enforce numeric inputs and arity, preventing silent under‑calculations. `src/hmrc_tax_mcp/evaluator.py:111-146`, `src/hmrc_tax_mcp/evaluator.py:266-279`.
- Band validation is enforced at compile time, eliminating mis‑ordered or overlapping bands. `src/hmrc_tax_mcp/dsl/compiler.py:31-52`, `src/hmrc_tax_mcp/dsl/compiler.py:167-174`.
- Canonicalisation now validates both the recompiled DSL AST and the stored AST against the checksum. `src/hmrc_tax_mcp/validation/pipeline.py:163-212`.
- rUK income‑tax bands now explicitly require post‑PA taxable income, removing the earlier ambiguity. `src/hmrc_tax_mcp/registry/rules/2025-26/ruk/income_tax_bands.yaml:6-16`.

### 3. Issues Found
1. **Category:** AST Design / Correctness  \
   **Severity:** Medium  \
   **Description:** The AST schema and `parse_ast` do not include the new `NEG` node. This makes the schema incomplete relative to the parser/compiler/evaluator, and any code relying on `parse_ast` will reject valid ASTs containing unary negation. `src/hmrc_tax_mcp/ast/schema.py:186-215`, `src/hmrc_tax_mcp/dsl/parser.py:204-211`, `src/hmrc_tax_mcp/evaluator.py:183-191`.  \
   **Why it matters:** Schema validation and typed AST parsing can fail for valid DSL input, creating tooling inconsistencies and blocking downstream consumers.  \
   **Suggested fix:** Add a `NegNode` to the schema, include it in `ASTNode`, and extend `_map` in `parse_ast`.

2. **Category:** AST Design / Safety  \
   **Severity:** Low  \
   **Description:** `ConstNode` still allows `str` and `None`, but the DSL parser rejects strings and the evaluator only handles numeric/bool constants. This leaves a mismatch between schema and execution. `src/hmrc_tax_mcp/ast/schema.py:26-30`, `src/hmrc_tax_mcp/dsl/parser.py:224-229`, `src/hmrc_tax_mcp/evaluator.py:67-73`.  \
   **Why it matters:** External or hand‑crafted ASTs can pass schema validation and then fail at runtime, undermining safety guarantees.  \
   **Suggested fix:** Narrow `ConstNode.value` to `int | float | bool` (and optionally `Decimal`), or add a strict AST validation pass that rejects non‑numeric constants before evaluation.

3. **Category:** Correctness / Testing  \
   **Severity:** Medium  \
   **Description:** New behaviors lack tests: sequential `LET` evaluation, band validation errors, `NEG`, `round`, and the new checksum check against `rule.ast` are not covered by unit tests. No tests confirm that invalid bands or AST/DSL mismatches fail validation. `tests/unit/test_validation.py`, `tests/unit/test_registry.py` (no coverage for new paths).  \
   **Why it matters:** These are safety‑critical behaviors; missing tests increase the risk of regressions and silent miscalculation.  \
   **Suggested fix:** Add unit tests for `NEG` and `round`, band validation failures, and a regression test where `rule.ast` diverges from `dsl_source` and stage 3 fails.

4. **Category:** Correctness (Tax Precision)  \
   **Severity:** Low  \
   **Description:** A `round()` function exists, but no policy enforces or documents when rules must apply it. Existing rules still return raw `Decimal` results without rounding guidance. `src/hmrc_tax_mcp/evaluator.py:247-261`.  \
   **Why it matters:** UK tax computations often require rounding at specific steps; without a policy, rule authors may implement inconsistent rounding.  \
   **Suggested fix:** Document a rounding policy (per rule or global), and add worked‑example tests that assert rounding behavior. Optionally require `round()` in rules that produce monetary outputs.

### 4. Suggested Refactorings
- Update AST schema to fully mirror runtime support (`NEG`) and tighten `CONST` types. `src/hmrc_tax_mcp/ast/schema.py`.
- Add a focused test suite for the new evaluator/compiler paths (negation, rounding, band validation, AST/DSL checksum mismatch). `tests/unit/test_validation.py` or new targeted tests.
- Document rounding expectations in the DSL spec and rule authoring guidelines.

### 5. Missing or Ambiguous Tax Rules
- **Composite rule orchestration** is still manual: PA taper + taxable income derivation + bands are not bundled into an end‑to‑end rule.
- **Dividend tax rates, NI, student loans, marriage allowance, blind person’s allowance** remain unimplemented.
- **CGT rate determination** is still simplified and does not model asset class or remaining basic‑rate band.
- No explicit **residency/tax‑year boundary** switching logic.

### 6. Final Recommendation
**Requires minor revision before production use.** The critical correctness issues from the previous review appear fixed, but schema drift and test gaps remain. Addressing the remaining issues and adding targeted tests should bring the system to a production‑ready standard.
