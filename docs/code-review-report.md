# Deep Code Review — HMRC Tax MCP

### 1. Summary
The core architecture (DSL → AST → evaluator → registry + validation pipeline) is coherent and auditable, and the tests show a solid foundation for deterministic rule evaluation. However, there are several correctness and safety gaps that can silently miscalculate tax or allow AST/DSL divergence. The highest-risk issues are: incorrect `LET` binding semantics, weak type enforcement in arithmetic/logical evaluation, missing validation that stored AST matches DSL, and ambiguous semantics in the rUK income‑tax bands rule. Overall risk level: **medium–high**. The code is **not production‑ready** without targeted fixes.

### 2. Strengths
- Deterministic evaluation with `Decimal` and explicit recursion depth limits, plus trace support for auditability. `src/hmrc_tax_mcp/evaluator.py:18-233`.
- Canonicalisation and checksum system for structural integrity of ASTs. `src/hmrc_tax_mcp/ast/canonical.py`.
- DSL compiler and parser are clear and maintainable, with explicit grammar and well‑structured recursive descent. `src/hmrc_tax_mcp/dsl/parser.py`, `src/hmrc_tax_mcp/dsl/compiler.py`.
- Validation pipeline is staged and extensible; worked examples are supported and used in tests. `src/hmrc_tax_mcp/validation/pipeline.py`, `tests/unit/test_validation.py`.
- Rule registry is simple and discoverable, with worked examples for key rules and coverage for Scotland vs rUK. `src/hmrc_tax_mcp/registry/store.py`, `tests/unit/test_scotland_rules.py`.

### 3. Issues Found
1. **Category:** Evaluation Semantics / Correctness  \
   **Severity:** High  \
   **Description:** `LET` bindings are evaluated in the *outer* scope, so later bindings cannot reference earlier ones even though the DSL is sequential. `Evaluator` uses `self.eval()` (outer scope) when building bindings, then evaluates the body in a new evaluator. `src/hmrc_tax_mcp/evaluator.py:88-96`, compiler groups all `let` statements into one `LET` node. `src/hmrc_tax_mcp/dsl/compiler.py:51-79`.  \
   **Why it matters:** Any DSL rule with dependent bindings (common in tax computations) will silently compute wrong results. This is a correctness bug, not just a semantics choice.  \
   **Suggested fix:** Either compile sequential `let` statements into nested `LET` nodes, or change `Evaluator` to evaluate bindings sequentially in `new_scope` (evaluate each binding with an evaluator that includes previous bindings). Also enforce/validate that forward references are illegal if you keep current semantics.

2. **Category:** Python Quality / Safety / Correctness  \
   **Severity:** High  \
   **Description:** Arithmetic operators ignore non‑`Decimal` values and implicitly allow `bool` values without error. `ADD`/`SUB`/`MUL` filter out non‑`Decimal` inputs, producing silent under‑calculations; `DIV` can operate on `bool` or non‑numeric values (and doesn’t check arity). `src/hmrc_tax_mcp/evaluator.py:108-136`.  \
   **Why it matters:** Tax results can be silently wrong when a variable is boolean or a rule is malformed. This violates deterministic, auditable evaluation expectations.  \
   **Suggested fix:** Enforce numeric types for arithmetic nodes (reject `bool`, `str`, `None`), validate arg counts (e.g., `SUB`/`DIV` must have exactly 2 args or explicitly define n‑ary semantics), and fail fast with `EvaluationError` on type mismatches.

3. **Category:** Correctness / AST Design  \
   **Severity:** High  \
   **Description:** `BAND_APPLY` does not validate band ordering, overlap, or monotonic bounds. It assumes correct ordering and non‑overlap, but will still compute (potentially double‑taxing or skipping income) if bands are mis‑ordered or overlapping. `src/hmrc_tax_mcp/evaluator.py:177-193`, schema does not enforce constraints. `src/hmrc_tax_mcp/ast/schema.py:154-163`.  \
   **Why it matters:** Band rules are central to income tax, CGT, and allowances. A malformed band list could silently produce materially incorrect tax.  \
   **Suggested fix:** Validate bands at compile or validation time: ensure `lower` is strictly increasing, `upper` (if present) is > `lower`, and each band starts at the prior upper. Consider rejecting or normalising unsorted bands.

4. **Category:** Safety / Correctness  \
   **Severity:** High  \
   **Description:** Validation stage 3 checks only that the DSL recompiles to the stored checksum; it does **not** verify that `rule.ast` matches the DSL or checksum. A tampered AST can pass validation if the checksum remains aligned to the DSL. `src/hmrc_tax_mcp/validation/pipeline.py:161-189`.  \
   **Why it matters:** The system can execute an AST that does not correspond to the published DSL, defeating auditability and opening the door to silent miscalculation.  \
   **Suggested fix:** Compute checksum for both the recompiled DSL AST and the stored `rule.ast`, and require both to match the stored checksum. Additionally, compare canonicalised ASTs directly and fail on mismatch.

5. **Category:** AST Design / Correctness  \
   **Severity:** Medium  \
   **Description:** The DSL and schema allow `STRING` constants and `None` values, but the evaluator only supports numeric/bool values and will throw or misbehave if strings are used. `src/hmrc_tax_mcp/dsl/parser.py:215-219`, `src/hmrc_tax_mcp/ast/schema.py:27-30`, `src/hmrc_tax_mcp/evaluator.py:67-73`.  \
   **Why it matters:** The language surface suggests string support, but evaluation does not. This is a semantics mismatch likely to cause runtime errors.  \
   **Suggested fix:** Either implement string support (comparisons, equality, etc.) or remove string/None support from the parser and schema and enforce numeric/boolean constants in compilation.

6. **Category:** Correctness (UK Tax Logic)  \
   **Severity:** High  \
   **Description:** `income_tax_bands` for rUK is ambiguous about its input. The description says `taxable_income` is *after* personal allowance, but the nil‑rate band (0–£12,570) is also applied. This will under‑tax if the input really is post‑PA. `src/hmrc_tax_mcp/registry/rules/2025-26/ruk/income_tax_bands.yaml:6-16`.  \
   **Why it matters:** Misinterpreting the input here results in systematic under‑calculation of income tax.  \
   **Suggested fix:** Split into two rules (`gross_income` vs `taxable_income`) or change the DSL/description so the nil‑rate band is only included when the input is gross. Alternatively, remove the nil‑rate band and require PA to be applied elsewhere.

7. **Category:** Correctness (Tax Precision)  \
   **Severity:** Medium  \
   **Description:** There is no explicit rounding policy. UK tax computations typically require rounding at defined steps (often to the nearest penny or pound). The evaluator returns full `Decimal` precision with no rounding. `src/hmrc_tax_mcp/evaluator.py:18-233`.  \
   **Why it matters:** For rules involving percentages or chained calculations, penny‑level differences can accumulate and produce incorrect statutory results.  \
   **Suggested fix:** Define a rounding policy (per‑rule or global) and introduce a dedicated rounding node or post‑evaluation rounding step that is explicitly documented and tested.

8. **Category:** Correctness / Safety  \
   **Severity:** Medium  \
   **Description:** `get_rule(..., version="latest")` sorts versions lexicographically and can return an arbitrary jurisdiction when `jurisdiction` is omitted. `src/hmrc_tax_mcp/registry/store.py:44-75`.  \
   **Why it matters:** Version selection may pick the wrong rule (e.g., `1.0.10` vs `1.0.2`), and callers can receive a Scotland rule when they expected rUK.  \
   **Suggested fix:** Use semantic‑version parsing for ordering and require `jurisdiction` when multiple matches exist; otherwise raise a clear error.

9. **Category:** Python Quality / Safety  \
   **Severity:** Low  \
   **Description:** `CALL percent` assumes two arguments and does not validate arity; malformed DSL can cause `IndexError`. `src/hmrc_tax_mcp/evaluator.py:217-223`, compiler does not validate argument count. `src/hmrc_tax_mcp/dsl/compiler.py:107-118`.  \
   **Why it matters:** This weakens validation guarantees and yields non‑user‑friendly errors.  \
   **Suggested fix:** Enforce arity in the compiler and evaluator, and raise `EvaluationError` with clear messages.

10. **Category:** AST Design  \
    **Severity:** Low  \
    **Description:** The DSL lacks unary minus, so negative constants cannot be expressed. This limits the ability to model offsets, reliefs, and adjustments. `src/hmrc_tax_mcp/dsl/parser.py:204-208`.  \
    **Why it matters:** Future tax rules may require negative adjustments or rebates.  \
    **Suggested fix:** Implement unary minus in the parser and compiler and add evaluator support.

### 4. Suggested Refactorings
- Add a **type‑checking/validation pass** for ASTs (numeric vs boolean vs string), including arity checks and domain‑specific invariants (e.g., `BAND_APPLY` bands monotonicity). This should run during validation stage 2 or 3.
- Change compiler output for multi‑statement DSL to **nested `LET` nodes** (true sequential semantics), or explicitly document and enforce simultaneous binding semantics.
- Introduce a **RuleValidator** utility that compares `dsl_source`, `ast`, and `checksum` in a single canonical pass, reducing duplicated logic between compiler and pipeline.
- Add a **rounding policy layer**: either a dedicated `ROUND` node or a post‑evaluation normalisation step with configurable precision (e.g., pounds vs pennies).
- Replace version comparison with a semantic‑version parser and require explicit jurisdiction where collisions exist.

### 5. Missing or Ambiguous Tax Rules
- **Personal allowance handling** is ambiguous in `income_tax_bands` (gross vs net input). `src/hmrc_tax_mcp/registry/rules/2025-26/ruk/income_tax_bands.yaml:6-16`.
- No composite rule to **combine PA taper + bands + taxable income derivation**; users must manually stitch rules together, which risks misapplication.
- **Additional‑rate PSA (0 allowance)** is not represented; only basic/higher (and starter for Scotland) are defined.
- **Dividend tax rates** are not implemented (only the dividend allowance constant).
- **National Insurance, student loan, marriage allowance, blind person’s allowance,** and other common adjustments are absent.
- **CGT rate rules** are simplified to a single boolean; they do not model asset type, remaining basic rate band, or relief interactions.
- No explicit **tax‑year boundary logic** (6 April–5 April) or residency‑based rule switching.

### 6. Final Recommendation
**Requires revision before production use.** The core framework is solid, but the current evaluator semantics, validation gaps, and ambiguous rule definitions create material risk of silent miscalculation. Address the high‑severity issues above, tighten validation, and expand worked examples before relying on this for real‑world tax calculations.
