# Retirement & Later Life Tax Rules — Implementation Plan

## Problem Statement

The HMRC tax MCP needs a complete rule set to support retirement and later-life financial
planning scenarios. The current registry covers core income-tax mechanics well but is missing
rules across pension decumulation, inheritance tax, savings wrappers, and property — all of
which are central to retirement planning.

## Categorisation Approach

Rules are organised by **lifecycle stage** (when the rule matters) with a secondary grouping
by **tax type**. Each rule is assigned to exactly one stage; the stage order reflects typical
use in a retirement planning journey:

| Stage | When it matters |
|---|---|
| **A — Pension Decumulation** | Taking money out of pension pots |
| **B — Tax-Efficient Wrappers** | ISAs, investment bonds, premium bonds |
| **C — Income Allowances** | Allowances that reduce income tax in retirement |
| **D — State & Means-Tested Benefits** | State pension, pension credit |
| **E — Inheritance Tax** | Estate planning, gifting, death benefits |
| **F — Property** | Downsizing, SDLT, CGT on home disposal |
| **G — Pension Accumulation** | Still saving into pensions pre-retirement |
| **H — Care & Later Life** | Funding care, deprivation of assets |

Within each bucket rules are marked **P1 / P2 / P3** for implementation priority:
- **P1** — needed to answer the most common retirement planning questions
- **P2** — needed for comprehensive planning
- **P3** — specialist / edge-case scenarios

---

## What Already Exists ✅

(All available in 2025-26 rUK unless noted)

- `income_tax_bands` (rUK + Scotland), `income_tax_due`, `pa_taper`
- `dividend_allowance`, `dividend_income_bands`, `savings_income_bands`, `property_income_bands`
- `savings_allowance_basic/higher/additional` (+ Scotland starter)
- `is_higher_rate_taxpayer`
- `cgt_due`, `cgt_exempt`, `cgt_rates`, `gia_disposal_gain`
- `pension_lsa`, `pension_tapered_annual_allowance`, `money_purchase_annual_allowance`
- `pension_ufpls_tax_free_fraction`, `pension_ufpls_taxable_fraction`
- `state_pension_annual`

---

## Bucket A — Pension Decumulation

> Taking benefits from defined-contribution and defined-benefit pensions.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `pension_annual_allowance` | Standard AA (no taper, no MPAA) | Returns £60,000 |
| P1 | `pension_commencement_lump_sum` | Tax-free cash (PCLS) on crystallisation | 25% of the amount crystallised, capped at remaining LSA |
| P1 | `pension_lsa_remaining` | Unused Lump Sum Allowance after prior crystallisations | £268,275 − prior tax-free cash received |
| P2 | `pension_carry_forward` | Unused AA from prior 3 tax years available to carry forward | AA − pension input amount for each of the 3 preceding years |
| P2 | `pension_annual_allowance_effective` | Composite: picks standard AA, tapered AA, or MPAA | Delegates to taper / MPAA rules; returns the lowest applicable |
| P2 | `pension_small_pot_lump_sum` | Commutation of small pots (≤ £10k each, max 3 personal) | 25% tax-free; rest taxed as income; does NOT trigger MPAA |
| P2 | `pension_flexi_access_trigger` | Boolean: does this withdrawal type trigger MPAA? | True for FAD / UFPLS / flexible annuity; false for PCLS / annuity / small pots |
| P3 | `pension_commencement_excess_lump_sum` | Lump sum above LSA — fully taxed at marginal rate | Excess × marginal rate |
| P3 | `pension_serious_ill_health_lump_sum` | Commutation if life expectancy < 2 years; tax-free if under 75 | Boolean age + health conditions |
| P3 | `pension_death_benefit_lump_sum` | Tax treatment of lump-sum death benefit | Pre-75: tax-free (within LSA); post-75: taxed at recipient's marginal rate |
| P3 | `pension_estate_inclusion_2027` | Uncrystallised / drawdown funds included in estate from April 2027 | Boolean gate on tax year ≥ 2027-28; amount added to estate for IHT |

**Scotland note:** Pension rules are HMRC-set (not devolved) — rUK only, as per existing pattern.

---

## Bucket B — Tax-Efficient Wrappers

> ISAs, investment bonds, and other tax-sheltered products.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `isa_annual_allowance` | Maximum ISA subscription per tax year | £20,000 (frozen 2025-26 through 2030-31) |
| P1 | `isa_income_tax_due` | Income from ISA is tax-free | Returns 0 — used to confirm no tax on ISA income |
| P1 | `isa_cgt_due` | Gains within ISA are tax-free | Returns 0 |
| P2 | `lifetime_isa_annual_bonus` | 25% government bonus on LISA contributions | 25% of min(contributions, £4,000); max bonus £1,000/year |
| P2 | `lifetime_isa_withdrawal_penalty` | Charge on unauthorised LISA withdrawal | 25% of withdrawal amount (recovers bonus + erodes 6.25% of principal) |
| P2 | `investment_bond_chargeable_gain` | Chargeable event gain on onshore/offshore bond | Gain = proceeds − premium paid; top-sliced over years held |
| P2 | `investment_bond_top_slicing_relief` | Reduces tax on chargeable gain by spreading over policy years | (Full tax − tax on slice) × number of years |
| P3 | `investment_bond_time_apportionment` | Offshore bond partial exemption for non-UK resident years | Gain × UK years / total years |

---

## Bucket C — Income Allowances

> Allowances that reduce income tax liability in retirement.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `marriage_allowance` | Transfer up to £1,260 of PA from non-taxpayer to basic-rate spouse | Tax saving = £252; conditions: recipient must be basic-rate payer |
| P1 | `marriage_allowance_eligible` | Boolean eligibility test for marriage allowance | Transferor income ≤ PA; recipient is basic-rate taxpayer |
| P2 | `blind_persons_allowance` | Additional allowance for registered blind persons | £3,070 (2025-26); added to PA |
| P3 | `rent_a_room_allowance` | Tax-free threshold for renting a furnished room | £7,500/year; relevant for retirees letting a room |
| P3 | `trading_allowance` | Tax-free threshold for casual/hobby income | £1,000/year |
| P3 | `property_allowance` | Tax-free threshold for property income | £1,000/year; alternative to expenses basis |

---

## Bucket D — State & Means-Tested Benefits

> State entitlements affecting retirement income.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `state_pension_weekly` | Full new state pension weekly amount | £230.25/week (2025-26 est.) — reference value |
| P2 | `pension_credit_standard_minimum_guarantee` | Minimum weekly income guaranteed for pensioners | Single: £218.15/week (2025-26); couple: £332.95/week |
| P2 | `pension_credit_savings_credit` | Top-up for pensioners with modest savings (pre-2016 SP only) | Complex means-test; being phased out for new claimants |
| P3 | `national_insurance_qualifying_years` | State pension entitlement based on NI record | 35 qualifying years for full new SP; 10 minimum |

---

## Bucket E — Inheritance Tax

> Estate planning, gifting strategies, and death-benefit treatment.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `iht_nil_rate_band` | Standard NRB — first slice of estate chargeable at 0% | £325,000 (frozen to 2030) |
| P1 | `iht_residence_nil_rate_band` | RNRB on main residence passing to direct descendants | Up to £175,000 (frozen to 2030) |
| P1 | `iht_due` | IHT payable on death estate | 40% on (estate − NRB − RNRB); 36% if ≥ 10% to charity |
| P1 | `iht_transferable_nil_rate_band` | Spouse/CP can inherit unused NRB | Up to 2× NRB for surviving spouse (£650,000 combined) |
| P2 | `iht_rnrb_taper` | RNRB reduces for estates > £2m | £1 per £2 above £2m; fully withdrawn at £2.35m |
| P2 | `iht_annual_gift_exemption` | Gifts up to £3,000/year are immediately exempt | Carry-forward 1 year only; combined max £6,000 |
| P2 | `iht_small_gifts_exemption` | Gifts up to £250 per recipient per year | Unlimited number of recipients; cannot combine with annual exemption for same person |
| P2 | `iht_taper_relief` | Reduces IHT on gifts made 3-7 years before death | 20/40/60/80% reduction on tax due; no relief on first £325,000 of gifts |
| P2 | `iht_potentially_exempt_transfer` | PET becomes chargeable if donor dies within 7 years | Gift amount + taper-relief calculation |
| P2 | `iht_normal_expenditure_income` | Gifts from regular surplus income are immediately exempt | Must be habitual, from income, and leave donor with adequate standard of living |
| P3 | `iht_charity_reduced_rate` | 36% rate when ≥ 10% of net estate left to charity | Conditional rate rule |
| P3 | `iht_business_property_relief` | 50% or 100% relief on qualifying business assets | 100%: unquoted shares, trading businesses; 50%: quoted shares, land used by partnership |
| P3 | `iht_pension_estate_inclusion_2027` | Pension funds included in IHT estate from April 2027 | Links to Bucket A P3 rule; applies to uncrystallised funds and drawdown |

---

## Bucket F — Property

> Retirement-related property transactions (downsizing, letting, disposal of home).

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `private_residence_relief` | CGT exemption on disposal of main home | Full exemption if always main residence; partial if let / absent periods |
| P1 | `prr_letting_relief` | Letting relief on CGT when home was let | Capped at lower of: PRR, gain from letting period, £40,000 — only if shared occupancy |
| P2 | `sdlt_residential` | SDLT on residential property purchase in England/NI | 0% up to £250k, 5% £250k-£925k, 10% £925k-£1.5m, 12% above (2025-26) |
| P2 | `sdlt_higher_rates` | 3pp surcharge for additional dwellings / non-UK residents | Added to standard SDLT bands |
| P2 | `iht_rnrb_downsizing_addition` | RNRB preserved when downsizing from larger home after 8 Jul 2015 | Complex; preserves RNRB lost on downsizing |
| P3 | `lbtt_residential` | Land & Buildings Transaction Tax (Scotland equivalent of SDLT) | Scotland-specific bands |

---

## Bucket G — Pension Accumulation (Pre-Retirement)

> Rules for the accumulation phase; still relevant for later-life planners with active pensions.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P1 | `pension_tax_relief_basic_rate` | Basic-rate relief added to personal pension contributions | Contribution × (1 / (1 − 0.20)); i.e. for every £80 paid, £100 goes in |
| P2 | `pension_tax_relief_higher_rate` | Additional relief via self-assessment for higher/additional rate payers | Higher/additional rate − basic rate × gross contribution |
| P2 | `pension_net_pay_arrangement` | Net pay: employer deducts contribution before PAYE | Employee gets relief at marginal rate automatically; no self-assessment needed |
| P3 | `pension_employer_contribution` | Employer contributions count toward AA; not taxed as benefit | Added to pension input amount |

---

## Bucket H — Care & Later Life

> Funding social care; deprivation of assets rules.

| Priority | Rule ID | Description | Key values / logic |
|---|---|---|---|
| P2 | `care_home_capital_threshold_england` | Capital limit above which full care costs must be self-funded (England) | £23,250 upper threshold; £14,250 lower (partial contribution) |
| P2 | `care_home_capital_threshold_scotland` | Scotland care capital threshold | £32,750 upper; £19,500 lower (2025-26) — devolved |
| P3 | `care_home_notional_capital` | Deprivation of assets: disregarded transfer treated as notional capital | If asset transferred to avoid care fees, its value still counted |

---

## Implementation Priority Summary

| Priority | Bucket | Count | Rationale |
|---|---|---|---|
| **P1 now** | A (Decumulation), B (ISAs), C (Allowances) | ~12 rules | Needed to answer any basic retirement income question |
| **P1 next** | E (IHT core), D (State benefits), F (PRR + SDLT) | ~10 rules | Estate planning and property are most common retirement advice topics |
| **P2** | E (IHT gifting), F (SDLT), B (Bonds), G (Accumulation) | ~18 rules | Comprehensive planning scenarios |
| **P3** | All specialist / edge cases | ~12 rules | Specialist scenarios — implement on demand |

**Suggested first sprint:** Bucket A P1 (PCLS + LSA remaining + annual AA composite) + Bucket B P1 (ISA allowance + zero-tax wrappers) + Bucket C P1 (marriage allowance) + Bucket E P1 (IHT NRB + RNRB + iht_due).

---

## Notes

- All rules span 2025-26 through 2030-31 (or later as announced) following existing pattern.
- Scotland variants required for: income tax (already exists), LBTT (Bucket F P3), care thresholds (Bucket H P2), savings allowance (already exists).
- IHT pension changes from April 2027 (`pension_estate_inclusion_2027`) are significant — flag as a time-sensitive P3 with an effective-date gate in the DSL.
- Marriage allowance eligibility depends on `pa_taper` and `is_higher_rate_taxpayer` rules already in registry.
