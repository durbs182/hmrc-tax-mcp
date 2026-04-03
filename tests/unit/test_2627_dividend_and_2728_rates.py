"""
Tests for Finance Bill 2025-26 rate changes:
  - dividend_income_bands (2026-27+): new rates 10.75% / 35.75% / 39.35%
  - savings_income_bands (2027-28+): new rates 22% / 42% / 47%
  - property_income_bands (2027-28+): new rates 22% / 42% / 47%
  - income_tax_due multi-stream composite (2027-28+)
"""

from __future__ import annotations

from decimal import Decimal

from hmrc_tax_mcp.evaluator import Evaluator
from hmrc_tax_mcp.registry.store import get_rule

# ─── dividend_income_bands ────────────────────────────────────────────────────


class TestDividendIncomeBands2627:
    """2026-27 dividend rates: 10.75% ordinary / 35.75% upper / 39.35% additional."""

    def _eval(self, dividend_income: float, income_before: float, jur: str = "rUK") -> Decimal:
        entry = get_rule("dividend_income_bands", jurisdiction=jur, tax_year="2026-27")
        assert entry is not None
        return Evaluator(
            variables={
                "dividend_income": Decimal(str(dividend_income)),
                "income_before": Decimal(str(income_before)),
            }
        ).eval(entry.ast)

    def test_basic_rate_taxpayer(self) -> None:
        """£2,000 dividends, £30k prior income → DA deducted → £1,500 @ 10.75% = £161.25."""
        result = self._eval(2000, 30000)
        assert result == Decimal("161.25")

    def test_higher_rate_taxpayer(self) -> None:
        """£5,000 dividends, £60k prior income → £4,500 taxable all at 35.75% = £1,608.75."""
        result = self._eval(5000, 60000)
        assert result == Decimal("1608.75")

    def test_additional_rate_taxpayer(self) -> None:
        """£3,000 dividends, £130k prior income → £2,500 taxable @ 39.35% = £983.75."""
        result = self._eval(3000, 130000)
        assert result == Decimal("983.75")

    def test_dividend_allowance_absorbs_small_dividend(self) -> None:
        """£500 dividends → all within £500 DA → £0 tax."""
        result = self._eval(500, 30000)
        assert result == Decimal("0.00")

    def test_straddles_basic_higher_boundary(self) -> None:
        """Dividends crossing from basic to upper rate band."""
        # income_before=49270, dividend=5000, DA=500, taxable=4500
        # start=49270, end=53770
        # basic_portion = min(53770,50270)-max(49270,12570) = 50270-49270 = 1000
        # upper_portion = min(53770,125140)-max(49270,50270) = 53770-50270 = 3500
        # tax = 1000*0.1075 + 3500*0.3575 = 107.50 + 1251.25 = 1358.75
        result = self._eval(5000, 49270)
        assert result == Decimal("1358.75")

    def test_zero_dividends(self) -> None:
        result = self._eval(0, 40000)
        assert result == Decimal("0.00")

    def test_scotland_same_rates(self) -> None:
        """Dividend rates are set at UK level — Scotland matches rUK."""
        ruk = self._eval(2000, 30000, jur="rUK")
        scot = self._eval(2000, 30000, jur="scotland")
        assert ruk == scot == Decimal("161.25")

    def test_2027_28_same_rates(self) -> None:
        """Dividend rates unchanged in 2027-28 vs 2026-27."""
        entry_2627 = get_rule("dividend_income_bands", jurisdiction="rUK", tax_year="2026-27")
        entry_2728 = get_rule("dividend_income_bands", jurisdiction="rUK", tax_year="2027-28")
        assert entry_2627 is not None and entry_2728 is not None
        assert entry_2627.checksum == entry_2728.checksum


# ─── savings_income_bands ─────────────────────────────────────────────────────


class TestSavingsIncomeBands2728:
    """2027-28 savings income rates: 22% basic / 42% higher / 47% additional."""

    def _eval(
        self, savings_income: float, income_before: float, tax_year: str = "2027-28",
        jur: str = "rUK"
    ) -> Decimal:
        entry = get_rule("savings_income_bands", jurisdiction=jur, tax_year=tax_year)
        assert entry is not None
        return Evaluator(
            variables={
                "savings_income": Decimal(str(savings_income)),
                "income_before": Decimal(str(income_before)),
            }
        ).eval(entry.ast)

    def test_basic_rate_taxpayer_with_psa(self) -> None:
        """£2,000 savings, £40k prior income → PSA=£1,000 → £1,000 taxable @ 22% = £220."""
        result = self._eval(2000, 40000)
        assert result == Decimal("220.00")

    def test_higher_rate_taxpayer_psa_500(self) -> None:
        """£5,000 savings, £55k prior income → PSA=£500 → £4,500 taxable @ 42% = £1,890."""
        result = self._eval(5000, 55000)
        assert result == Decimal("1890.00")

    def test_additional_rate_no_psa(self) -> None:
        """£10,000 savings, £130k prior income → PSA=£0 → £10,000 taxable @ 47% = £4,700."""
        result = self._eval(10000, 130000)
        assert result == Decimal("4700.00")

    def test_savings_entirely_within_psa(self) -> None:
        """£800 savings, basic-rate taxpayer → entirely within £1,000 PSA → £0 tax."""
        result = self._eval(800, 25000)
        assert result == Decimal("0.00")

    def test_straddles_basic_higher_boundary(self) -> None:
        """Savings crossing from basic to higher band."""
        # income_before=49000, savings=3000; PSA: 49000<50270 → basic → PSA=1000
        # savings_taxable=2000; start=49000, end=51000
        # basic_portion=min(51000,50270)-max(49000,12570)=50270-49000=1270 @ 22%
        # higher_portion=min(51000,125140)-max(49000,50270)=51000-50270=730 @ 42%
        # tax=1270*0.22 + 730*0.42 = 279.40+306.60 = 586.00
        result = self._eval(3000, 49000)
        assert result == Decimal("586.00")

    def test_scotland_same_rates(self) -> None:
        """Savings income rates apply UK-wide including Scotland."""
        ruk = self._eval(2000, 40000, jur="rUK")
        scot = self._eval(2000, 40000, jur="scotland")
        assert ruk == scot == Decimal("220.00")

    def test_frozen_years_consistent(self) -> None:
        """2028-29, 2029-30, 2030-31 savings rates are frozen at 2027-28 levels."""
        base = get_rule("savings_income_bands", jurisdiction="rUK", tax_year="2027-28")
        assert base is not None
        for yr in ("2028-29", "2029-30", "2030-31"):
            entry = get_rule("savings_income_bands", jurisdiction="rUK", tax_year=yr)
            assert entry is not None, f"Missing savings_income_bands for {yr}"
            assert entry.checksum == base.checksum, f"Rate mismatch for {yr}"


# ─── property_income_bands ────────────────────────────────────────────────────


class TestPropertyIncomeBands2728:
    """2027-28 property income rates: 22% basic / 42% higher / 47% additional."""

    def _eval(
        self, property_income: float, income_before: float, tax_year: str = "2027-28"
    ) -> Decimal:
        entry = get_rule("property_income_bands", jurisdiction="rUK", tax_year=tax_year)
        assert entry is not None
        return Evaluator(
            variables={
                "property_income": Decimal(str(property_income)),
                "income_before": Decimal(str(income_before)),
            }
        ).eval(entry.ast)

    def test_all_in_basic_rate_band(self) -> None:
        """£10k property, £30k employment → all in basic band → 10000*22% = £2,200."""
        result = self._eval(10000, 30000)
        assert result == Decimal("2200.00")

    def test_all_in_higher_rate_band(self) -> None:
        """£5k property, £60k employment → all above £50,270 → 5000*42% = £2,100."""
        result = self._eval(5000, 60000)
        assert result == Decimal("2100.00")

    def test_straddles_basic_higher_boundary(self) -> None:
        """£10k property, £48k employment → straddles basic/higher boundary."""
        # start=48000, end=58000
        # basic=max(min(58000,50270)-max(48000,12570),0)=50270-48000=2270 @ 22%
        # higher=max(min(58000,125140)-max(48000,50270),0)=58000-50270=7730 @ 42%
        # tax=2270*0.22+7730*0.42=499.40+3246.60=3746.00
        result = self._eval(10000, 48000)
        assert result == Decimal("3746.00")

    def test_additional_rate_band(self) -> None:
        """£10k property, £130k employment → all above £125,140 → £4,700."""
        result = self._eval(10000, 130000)
        assert result == Decimal("4700.00")

    def test_straddles_higher_additional_boundary(self) -> None:
        """£10k property, £120k employment → straddles higher/additional boundary."""
        # start=120000, end=130000
        # basic=max(min(130000,50270)-max(120000,12570),0)=0 (120000>50270)
        # higher=max(min(130000,125140)-max(120000,50270),0)=125140-120000=5140 @ 42%
        # additional=max(130000-max(120000,125140),0)=130000-125140=4860 @ 47%
        # tax=5140*0.42+4860*0.47=2158.80+2284.20=4443.00
        result = self._eval(10000, 120000)
        assert result == Decimal("4443.00")

    def test_zero_property_income(self) -> None:
        result = self._eval(0, 40000)
        assert result == Decimal("0.00")

    def test_not_available_for_scotland(self) -> None:
        """Property income rates are Scottish Parliament jurisdiction — no rule for Scotland."""
        result = get_rule(
            "property_income_bands", jurisdiction="scotland", tax_year="2027-28"
        )
        assert result is None

    def test_frozen_years_consistent(self) -> None:
        """Rates frozen through 2030-31."""
        base = get_rule("property_income_bands", jurisdiction="rUK", tax_year="2027-28")
        assert base is not None
        for yr in ("2028-29", "2029-30", "2030-31"):
            entry = get_rule("property_income_bands", jurisdiction="rUK", tax_year=yr)
            assert entry is not None, f"Missing property_income_bands for {yr}"
            assert entry.checksum == base.checksum, f"Rate mismatch for {yr}"


# ─── income_tax_due 2027-28 multi-stream composite ───────────────────────────


class TestIncomeTaxDueMultiStream2728:
    """2027-28 multi-stream income_tax_due composite rule."""

    def _eval(
        self,
        employment_income: float = 0,
        property_income: float = 0,
        savings_income: float = 0,
        dividend_income: float = 0,
        tax_year: str = "2027-28",
    ) -> Decimal:
        entry = get_rule("income_tax_due", jurisdiction="rUK", tax_year=tax_year)
        assert entry is not None
        return Evaluator(
            variables={
                "employment_income": Decimal(str(employment_income)),
                "property_income": Decimal(str(property_income)),
                "savings_income": Decimal(str(savings_income)),
                "dividend_income": Decimal(str(dividend_income)),
            }
        ).eval(entry.ast)

    def test_employment_only_basic_rate(self) -> None:
        """£30k employment only → same as 2026-27 single-stream for employment income."""
        # emp_taxable=30000-12570=17430; emp_basic=17430*0.20=3486.00
        result = self._eval(employment_income=30000)
        assert result == Decimal("3486.00")

    def test_employment_only_higher_rate(self) -> None:
        """£60k employment → basic 37700*20% + higher 9730*40% = 7540+3892 = 11432."""
        result = self._eval(employment_income=60000)
        assert result == Decimal("11432.00")

    def test_employment_plus_dividends_basic_rate(self) -> None:
        """£40k employment + £2k dividends → emp tax + dividend tax."""
        # emp_taxable=40000-12570=27430; emp_tax=27430*0.20=5486
        # div_gross=2000 (all PA consumed); div_taxable=max(2000-500,0)=1500
        # div stacked at 27430 → 28930 (all basic band); div_tax=1500*0.1075=161.25
        # total=5486+161.25=5647.25
        result = self._eval(employment_income=40000, dividend_income=2000)
        assert result == Decimal("5647.25")

    def test_employment_plus_savings_basic_rate(self) -> None:
        """£40k employment + £2k savings → PSA=£1k (basic rate) → £1k @ 22% = £220."""
        # emp_tax = 27430*0.20 = 5486
        # PSA: non_sav_taxable=27430<37700 → basic → PSA=1000
        # sav_taxable=max(2000-1000,0)=1000; stacked at 27430 → 28430
        # sav_basic=min(28430,37700)-27430=1000 @ 22%=220
        # total=5486+220=5706.00
        result = self._eval(employment_income=40000, savings_income=2000)
        assert result == Decimal("5706.00")

    def test_employment_plus_property(self) -> None:
        """£40k employment + £8k property → property taxes at 22% (all basic band)."""
        # emp_taxable=27430; emp_tax=27430*0.20=5486
        # prop_taxable=8000 (all PA consumed by employment)
        # prop stacked: 27430→35430; prop_basic=8000 @ 22%=1760
        # total=5486+1760=7246.00
        result = self._eval(employment_income=40000, property_income=8000)
        assert result == Decimal("7246.00")

    def test_all_four_streams_basic_rate(self) -> None:
        """All four income streams, all in basic rate band."""
        # emp=20000, prop=5000, sav=2000, div=3000
        # total=30000; PA=12570; emp_taxable=7430; prop_taxable=5000
        # non_sav=12430<37700 → PSA=1000; sav_taxable=max(2000-1000,0)=1000
        # div_taxable=max(3000-500,0)=2500
        # emp_tax=7430*0.20=1486
        # prop stacked 7430→12430; prop_basic=5000 @ 22%=1100
        # sav stacked 12430→13430; sav_basic=1000 @ 22%=220
        # div stacked 13430→15930; div_basic=2500 @ 10.75%=268.75
        # total=1486+1100+220+268.75=3074.75
        result = self._eval(
            employment_income=20000, property_income=5000,
            savings_income=2000, dividend_income=3000
        )
        assert result == Decimal("3074.75")

    def test_higher_rate_savings_psa_500(self) -> None:
        """Higher-rate taxpayer: savings PSA = £500."""
        # emp=60000, sav=5000
        # emp_taxable=47430; non_sav=47430>37700 → PSA=500
        # sav_taxable=max(5000-500,0)=4500
        # emp_tax=37700*0.20+(47430-37700)*0.40=7540+3892=11432 (... wait)
        # emp_basic=min(47430,37700)=37700 @ 20%=7540
        # emp_higher=max(min(47430,higher_limit)-37700,0): higher_limit=125140-12570=112570
        # =min(47430,112570)-37700=47430-37700=9730 @ 40%=3892
        # emp_tax=7540+3892=11432
        # sav stacked 47430→51930; sav_basic=max(min(51930,37700)-47430,0)=0
        # sav_higher=max(min(51930,112570)-max(47430,37700),0)=51930-47430=4500 @ 42%=1890
        # total=11432+1890=13322.00
        result = self._eval(employment_income=60000, savings_income=5000)
        assert result == Decimal("13322.00")

    def test_pa_taper_high_income(self) -> None:
        """£110k employment → PA tapers to £7,570; same as 2026-27 single-stream rule."""
        # emp=110000; total=110000; PA=12570-(110000-100000)/2=12570-5000=7570
        # emp_taxable=102430; higher_limit=125140-7570=117570
        # emp_basic=37700*0.20=7540; emp_higher=(102430-37700)*0.40=25892; total=33432
        result = self._eval(employment_income=110000)
        assert result == Decimal("33432.00")

    def test_zero_all_streams(self) -> None:
        result = self._eval()
        assert result == Decimal("0.00")

    def test_frozen_years_consistent(self) -> None:
        """2028-29 through 2030-31 use the same multi-stream rule."""
        base = get_rule("income_tax_due", jurisdiction="rUK", tax_year="2027-28")
        assert base is not None
        for yr in ("2028-29", "2029-30", "2030-31"):
            entry = get_rule("income_tax_due", jurisdiction="rUK", tax_year=yr)
            assert entry is not None, f"Missing income_tax_due for {yr}"
            assert entry.checksum == base.checksum, f"Mismatch for {yr}"
