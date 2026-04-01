# Rounding Policy for HMRC Tax Rules

## Overview

HMRC computations require deterministic, auditable rounding. This policy defines
when and how rounding must be applied in DSL rules and the evaluator.

## Evaluator Behaviour

- All arithmetic operates on `decimal.Decimal` with no implicit rounding.
- Raw `Decimal` results are exact until an explicit `round()` call is made.
- The `round(value, places)` function uses `ROUND_HALF_UP` (commercial rounding),
  matching HMRC's documented rounding convention.

## When to Apply `round()`

| Output type | Rounding requirement |
|-------------|----------------------|
| Tax liability (£) | Round down to nearest penny — use `round(result, 2)` |
| Tax-free cash (25% UFPLS) | Round down to nearest penny — use `round(result, 2)` |
| Personal allowance taper | No rounding; the taper formula produces whole pounds naturally |
| Percentage of income | Round to 2 decimal places before further use if intermediate result feeds a band |
| Band tax per slice | Round each slice result to 2 decimal places, sum, then round total to 2 decimal places |

## Rule Authoring Guidance

1. **Monetary outputs must call `round()`.**
   Every rule that produces a sterling amount payable to or from HMRC must wrap
   its final expression in `round(…, 2)`.

   ```
   # Good
   round(band_apply taxable_income: …, 2)

   # Bad — returns raw Decimal with arbitrary precision
   band_apply taxable_income: …
   ```

2. **Intermediate values do not need rounding** unless passed to a worked example
   that asserts a specific integer/penny amount.

3. **Worked examples should assert rounded values.** Use the `tolerance` field
   (in `WorkedExample`) only for comparison tests where HMRC source material gives
   an approximate figure.

4. **Do not use Python `round()` or float arithmetic in rule YAML/DSL.** All
   rounding must go through the evaluator's `round()` call function to guarantee
   `ROUND_HALF_UP` semantics.

## Reference

- HMRC Self Assessment: rounding rules — tax is rounded down to the nearest penny.
- Python `decimal` module: `ROUND_HALF_UP` rounds 0.5 away from zero.
- DSL `round()` implementation: `src/hmrc_tax_mcp/evaluator.py` — `TestCall` handles `"round"`.
