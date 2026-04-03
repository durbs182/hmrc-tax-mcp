# Known Policy Gaps

Rules in this engine are **only added once they are enacted in legislation** or
published as formal HMRC guidance.  This file records political commitments or
announced-but-not-yet-legislated changes so they are not forgotten and can be
picked up promptly once the relevant Finance Bill or statutory instrument
publishes.

---

## Pensioner Guarantee — state pension / personal allowance interaction

**Status:** Political commitment only — not in legislation as of April 2026.

**Trigger date:** Autumn Budget, November 2025 (Chancellor Rachel Reeves).

**What was committed:**
Pensioners whose *sole* income is the new state pension will not be required to
pay income tax on the amount by which the state pension exceeds the personal
allowance, for the remainder of this Parliament (expected to cover at least
tax years 2027-28 through 2030-31).

**Why it matters to this engine:**
The personal allowance is frozen at £12,570 until 5 April 2031.  Under the
triple lock the state pension is projected to exceed that threshold in 2027-28:

| Tax year | State pension (est.) | Personal allowance | Excess |
|---|---|---|---|
| 2025-26 | £11,973.00 | £12,570 | — |
| 2026-27 | £12,547.60 | £12,570 | — (£22.40 headroom) |
| 2027-28 | ~£13,100+ | £12,570 | ~£530+ would be taxable |

Without the guarantee, a pensioner with no other income would face a tax
liability on the excess.  The commitment means that HMRC will not collect tax
in this scenario — but the *mechanism* (targeted exemption, PAYE code
adjustment, statutory credit, or other instrument) has not been specified.

**What is NOT covered:**
- Pensioners with any other taxable income (private/workplace pension, SERPS /
  additional state pension, savings interest, dividends) are not exempt.  Their
  total income is assessed normally against the £12,570 allowance.

**Sources:**
- The Independent, 28 Nov 2025: "Reeves vows state pensioners won't have to pay
  tax despite alarm over…" — https://www.independent.co.uk/news/uk/politics/pension-reeves-budget-income-tax-martin-lewis-b2874251.html
- The Telegraph, 28 Nov 2025: "Rachel Reeves 'creates two-tier tax system' for
  pensioners" — https://www.telegraph.co.uk/business/2025/11/28/state-pensions-to-be-shielded-from-reevess-tax-rises/
- The Argus, Nov 2025: "Rachel Reeves confirms millions of pensioners to avoid
  HMRC tax" — https://www.theargus.co.uk/news/national/uk-today/25940704.rachel-reeves-confirms-millions-pensioners-avoid-hmrc-tax/

**TODO:** Revisit after the **Spring 2026 Finance Bill**.  Once the legislative
mechanism is published, add a new rule (candidate ID:
`state_pension_tax_exemption`) or a modifier to the `personal_allowance` rule,
with a corresponding worked example and validation test.  Check:
- legislation.gov.uk for the Finance Act / SI
- HMRC technical guidance (Employment Income Manual or Savings & Investment
  Manual) for operational detail
- HMRC PAYE coding notices for how the exemption is administered

---

## Finance Bill 2025-26 – ISA cash limit reduction (2027-28)

**Status:** Legislated (Finance Bill 2025-26), not yet modelled in this engine.

**Trigger date:** 6 April 2027.

**What changes:**
From 2027-28 the annual ISA cash subscription limit falls from £20,000 to £12,000 within
the overall £20,000 ISA allowance (so stocks-and-shares ISAs may receive the full £20,000 if
no cash ISA contribution is made). Customers aged 65 and over retain a £20,000 cash ISA limit.

**Why it matters to this engine:**
There is currently no ISA allowance rule in the registry. If one is added in future, the
2027-28 cash limit split should be reflected.

**TODO:** When an `isa_allowance` rule family is added, create:
- `isa_cash_limit` (2027-28+): £12,000 for under-65s, £20,000 for 65+
- `isa_total_limit` (unchanged): £20,000
- Update any composite rules that reference ISA headroom.

**Sources:**
- GOV.UK technical note: https://www.gov.uk/government/publications/changes-to-tax-rates-for-property-savings-and-dividend-income/change-to-tax-rates-for-property-savings-and-dividend-income-technical-note

---

## Finance Bill 2025-26 – Scotland property income rates (2027-28)

**Status:** Scottish Parliament jurisdiction — not covered by rUK rules.

**Trigger date:** 6 April 2027.

**What changes:**
The Finance Bill 2025-26 introduces separate property income tax rates for rUK
(England, Wales, Northern Ireland) of 22% / 42% / 47%. Property income taxation in
Scotland remains the responsibility of the Scottish Parliament; the Scottish rate for
property income has not yet been set for 2027-28.

**Why it matters to this engine:**
`property_income_bands` rules exist for rUK only (2027-28+). Scotland has no equivalent
rule. Any composite Scottish income tax rule that includes property income cannot be
completed until the Scottish Parliament publishes its rates.

**TODO:** Monitor Scottish Parliament Finance Bill announcements. Once published, add:
- `property_income_bands` for `scotland` jurisdiction (2027-28+)
- If a Scottish `income_tax_due` composite is added, update it to include property income.

**Sources:**
- GOV.UK technical note: https://www.gov.uk/government/publications/changes-to-tax-rates-for-property-savings-and-dividend-income/change-to-tax-rates-for-property-savings-and-dividend-income-technical-note

---

## Scotland – no composite income_tax_due rule

**Status:** Architectural gap — not modelled.

**What is missing:**
Scotland has no `income_tax_due` rule in any tax year. The Scottish income tax bands
(`income_tax_bands`, jurisdiction=scotland) exist and cover employment/trading income,
but there is no Scottish composite rule that combines the PA taper with band application,
nor one that handles savings and dividend income (which use UK rates).

**TODO:** Once requirements are clear, add `income_tax_due` for Scotland that:
- Uses Scottish employment income bands (starter/basic/intermediate/higher/advanced)
- Uses UK rates for savings income (savings_income_bands, same rules as rUK)
- Uses UK rates for dividend income (dividend_income_bands, same rules as rUK)
- Applies PA in the statutory ordering (employment → property → savings → dividends)

---

*Add new entries above this line in reverse-chronological order.*
