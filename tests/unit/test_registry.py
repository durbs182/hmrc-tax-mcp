"""Unit tests for the rule registry store."""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule, get_rule_snapshot, list_rules


def test_list_rules_returns_list() -> None:
    rules = list_rules()
    assert isinstance(rules, list)


def test_list_rules_contains_2025_26_rules() -> None:
    rules = list_rules()
    ids = {r.rule_id for r in rules}
    expected = {
        "income_tax_bands",
        "pa_taper",
        "cgt_exempt",
        "cgt_rates",
        "pension_lsa",
        "pension_ufpls_tax_free_fraction",
        "pension_ufpls_taxable_fraction",
        "state_pension_annual",
        "savings_allowance_basic",
        "savings_allowance_higher",
        "dividend_allowance",
        "savings_allowance_additional",
        "is_higher_rate_taxpayer",
        "income_tax_due",
        "cgt_due",
        "gia_disposal_gain",
    }
    assert expected.issubset(ids)


def test_get_rule_missing_returns_none() -> None:
    assert get_rule("nonexistent.rule", "1.0.0") is None


def test_get_rule_latest_missing_returns_none() -> None:
    assert get_rule("nonexistent.rule") is None


def test_get_rule_snapshot_returns_list() -> None:
    result = get_rule_snapshot("2025-26", "rUK")
    assert isinstance(result, list)


def test_get_rule_snapshot_contains_all_ruk_2025_26() -> None:
    result = get_rule_snapshot("2025-26", "rUK")
    ids = {r.rule_id for r in result}
    assert "income_tax_bands" in ids
    assert "pa_taper" in ids
    assert len(result) >= 11


def test_income_tax_bands_rule_checksum() -> None:
    entry = get_rule("income_tax_bands", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "8b039b0158b5b906334a76d2810cdf90a3bb29ef487788f81974bc2387bbe6b1"


def test_pa_taper_rule_checksum() -> None:
    entry = get_rule("pa_taper", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "a4f5132af3452c998f5175aa6f2df0049f1ff6d2cf2e0040dfa7a950ad5b00f8"


def test_pension_lsa_evaluates_correctly() -> None:
    entry = get_rule("pension_lsa", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("268275")


def test_cgt_exempt_evaluates_correctly() -> None:
    entry = get_rule("cgt_exempt", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("3000")


def test_income_tax_bands_evaluates_basic_rate() -> None:
    """£30,000 taxable income (post-PA) → £3,486 tax (20% on £17,430 above £12,570 threshold)."""
    entry = get_rule("income_tax_bands", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"taxable_income": Decimal("30000")}).eval(entry.ast)
    assert result == Decimal("3486")


def test_pa_taper_evaluates_partial_taper() -> None:
    """Income £110,000 → PA tapered to £7,570 (£10,000 excess → £5,000 reduction)."""
    entry = get_rule("pa_taper", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("110000")}).eval(entry.ast)
    assert result == Decimal("7570")


def test_cgt_rates_higher_rate() -> None:
    entry = get_rule("cgt_rates", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"is_higher_rate_taxpayer": True}).eval(entry.ast)
    assert result == Decimal("24")


def test_cgt_rates_basic_rate() -> None:
    entry = get_rule("cgt_rates", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"is_higher_rate_taxpayer": False}).eval(entry.ast)
    assert result == Decimal("18")


def test_state_pension_annual() -> None:
    entry = get_rule("state_pension_annual", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("11502.40")


# ---------------------------------------------------------------------------
# New rules: savings_allowance_additional, is_higher_rate_taxpayer,
#            income_tax_due, cgt_due, gia_disposal_gain
# ---------------------------------------------------------------------------

def test_savings_allowance_additional_is_zero() -> None:
    entry = get_rule("savings_allowance_additional", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator().eval(entry.ast)
    assert result == Decimal("0")


def test_savings_allowance_additional_checksum() -> None:
    entry = get_rule("savings_allowance_additional", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "82f934f547e5da82b60c09fa32890153d40d7bfaaff3664fc87d5fbf79e4e217"


def test_is_higher_rate_taxpayer_checksum() -> None:
    entry = get_rule("is_higher_rate_taxpayer", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "04ca80549dc1361ccf88b1b3126d498b536165ac388578f0c788b693069279cc"


def test_income_tax_due_checksum() -> None:
    entry = get_rule("income_tax_due", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "34ae672c2c67165e466a5e8e63526e3c6ea8515f8514f5edbf6057cab5452144"


def test_cgt_due_checksum() -> None:
    entry = get_rule("cgt_due", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "5c23ead756a880f5e46a9767b0f2931fea4c88fc0aa3a06900b6c0c749be0eb2"


def test_gia_disposal_gain_checksum() -> None:
    entry = get_rule("gia_disposal_gain", jurisdiction="rUK")
    assert entry is not None
    assert entry.checksum == "bbea96471b082ad1c76b0f10a7aa5c35986f1a7f3cc3c6508fae52e7e7fe4512"


def test_is_higher_rate_taxpayer_above_threshold() -> None:
    """Income £60,000 > £50,270 → True."""
    entry = get_rule("is_higher_rate_taxpayer", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("60000")}).eval(entry.ast)
    assert result is True


def test_is_higher_rate_taxpayer_at_threshold() -> None:
    """Income exactly £50,270 is NOT above threshold → False."""
    entry = get_rule("is_higher_rate_taxpayer", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("50270")}).eval(entry.ast)
    assert result is False


def test_is_higher_rate_taxpayer_below_threshold() -> None:
    """Income £30,000 < £50,270 → False."""
    entry = get_rule("is_higher_rate_taxpayer", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("30000")}).eval(entry.ast)
    assert result is False


def test_income_tax_due_basic_rate_only() -> None:
    """£30,000 income → effectivePA=12570, basic_band=17430 → tax £3,486."""
    entry = get_rule("income_tax_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("30000")}).eval(entry.ast)
    assert result == Decimal("3486.00")


def test_income_tax_due_higher_rate() -> None:
    """£60,000 → basic £7,540 + higher £3,892 = £11,432."""
    entry = get_rule("income_tax_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("60000")}).eval(entry.ast)
    # basic_band: 50270-12570=37700 @ 20% = 7540; higher_band: 60000-50270=9730 @ 40% = 3892
    assert result == Decimal("11432.00")


def test_income_tax_due_tapered_pa() -> None:
    """£110k → effectivePA=7570, taxable=102430, basic_band=37700, higher_band=64730 → £33,432."""
    entry = get_rule("income_tax_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("110000")}).eval(entry.ast)
    # taxable: 110000-7570=102430; basic: 37700*0.20=7540; higher: 64730*0.40=25892; total=33432
    assert result == Decimal("33432.00")


def test_income_tax_due_zero_income() -> None:
    entry = get_rule("income_tax_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(variables={"adjusted_net_income": Decimal("0")}).eval(entry.ast)
    assert result == Decimal("0")


def test_cgt_due_higher_rate_above_exempt() -> None:
    """£10,000 gain, higher-rate taxpayer → taxable £7,000 @ 24% = £1,680."""
    entry = get_rule("cgt_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(
        variables={"capital_gain": Decimal("10000"), "is_higher_rate_taxpayer": True}
    ).eval(entry.ast)
    assert result == Decimal("1680.00")


def test_cgt_due_basic_rate_above_exempt() -> None:
    """£8,000 gain, basic-rate taxpayer → taxable £5,000 @ 18% = £900."""
    entry = get_rule("cgt_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(
        variables={"capital_gain": Decimal("8000"), "is_higher_rate_taxpayer": False}
    ).eval(entry.ast)
    assert result == Decimal("900.00")


def test_cgt_due_within_exempt() -> None:
    """£2,500 gain is within £3,000 exempt → £0 tax."""
    entry = get_rule("cgt_due", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(
        variables={"capital_gain": Decimal("2500"), "is_higher_rate_taxpayer": False}
    ).eval(entry.ast)
    assert result == Decimal("0")


def test_gia_disposal_gain_proportional() -> None:
    """GIA value £10,000, base cost £6,000, draw £4,000.
    gain_fraction = 4000/10000 = 0.4; drawn=4000; gain = 1600."""
    entry = get_rule("gia_disposal_gain", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(
        variables={
            "market_value": Decimal("10000"),
            "base_cost": Decimal("6000"),
            "amount_drawn": Decimal("4000"),
        }
    ).eval(entry.ast)
    assert result == Decimal("1600.00")


def test_gia_disposal_gain_capped_at_market_value() -> None:
    """Drawing more than available is capped: draw £15,000 from £10,000 pot.
    drawn=10000; gain_fraction=0.4; gain=4000."""
    entry = get_rule("gia_disposal_gain", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(
        variables={
            "market_value": Decimal("10000"),
            "base_cost": Decimal("6000"),
            "amount_drawn": Decimal("15000"),
        }
    ).eval(entry.ast)
    assert result == Decimal("4000.00")


def test_gia_disposal_gain_no_gain_when_at_cost() -> None:
    """market_value == base_cost → gain_fraction = 0 → capital gain £0."""
    entry = get_rule("gia_disposal_gain", jurisdiction="rUK")
    assert entry is not None
    result = Evaluator(
        variables={
            "market_value": Decimal("10000"),
            "base_cost": Decimal("10000"),
            "amount_drawn": Decimal("5000"),
        }
    ).eval(entry.ast)
    assert result == Decimal("0")


# ---------------------------------------------------------------------------
# Jurisdiction defaulting — rules that exist in both rUK and scotland
# ---------------------------------------------------------------------------

class TestJurisdictionDefault:
    """
    When jurisdiction is omitted for a rule that exists in multiple jurisdictions,
    get_rule should silently default to rUK rather than raising ValueError.
    """

    def test_income_tax_bands_no_jurisdiction_returns_ruk(self) -> None:
        entry = get_rule("income_tax_bands")
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_pa_taper_no_jurisdiction_returns_ruk(self) -> None:
        entry = get_rule("pa_taper")
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_dividend_allowance_no_jurisdiction_returns_ruk(self) -> None:
        entry = get_rule("dividend_allowance")
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_savings_allowance_basic_no_jurisdiction_returns_ruk(self) -> None:
        entry = get_rule("savings_allowance_basic")
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_savings_allowance_higher_no_jurisdiction_returns_ruk(self) -> None:
        entry = get_rule("savings_allowance_higher")
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_explicit_scotland_jurisdiction_returns_scotland(self) -> None:
        entry = get_rule("income_tax_bands", jurisdiction="scotland")
        assert entry is not None
        assert entry.jurisdiction == "scotland"

    def test_explicit_ruk_jurisdiction_returns_ruk(self) -> None:
        entry = get_rule("income_tax_bands", jurisdiction="rUK")
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_specific_version_no_jurisdiction_returns_ruk(self) -> None:
        """Specific version path also defaults to rUK when jurisdiction is omitted."""
        ruk_entry = get_rule("income_tax_bands", jurisdiction="rUK")
        assert ruk_entry is not None
        entry = get_rule("income_tax_bands", version=ruk_entry.version)
        assert entry is not None
        assert entry.jurisdiction == "rUK"

    def test_ruk_only_rule_unaffected(self) -> None:
        """A rule that exists only in rUK is still returned without specifying jurisdiction."""
        entry = get_rule("cgt_exempt")
        assert entry is not None
        assert entry.jurisdiction == "rUK"
