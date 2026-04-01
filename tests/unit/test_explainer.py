"""Tests for the rule explainer."""

from __future__ import annotations

from hmrc_tax_mcp.explainer import _collect_variables, explain_rule
from hmrc_tax_mcp.registry.store import get_rule


def _rule(rule_id: str) -> dict:
    entry = get_rule(rule_id)
    assert entry is not None
    return entry.model_dump(mode="json")


class TestExplainRuleFields:
    def test_returns_required_keys(self) -> None:
        result = explain_rule(_rule("cgt_exempt"))
        for key in ("title", "description", "tax_year", "jurisdiction",
                    "dsl_source", "explanation", "variables", "citations",
                    "checksum", "version", "provenance"):
            assert key in result, f"Missing key: {key}"

    def test_title_populated(self) -> None:
        result = explain_rule(_rule("cgt_exempt"))
        assert "Capital Gains" in result["title"]

    def test_citations_populated(self) -> None:
        result = explain_rule(_rule("income_tax_bands"))
        assert len(result["citations"]) >= 1
        assert "url" in result["citations"][0]

    def test_checksum_preserved(self) -> None:
        entry = get_rule("income_tax_bands")
        assert entry is not None
        result = explain_rule(_rule("income_tax_bands"))
        assert result["checksum"] == entry.checksum

    def test_dsl_source_stripped(self) -> None:
        result = explain_rule(_rule("pa_taper"))
        # dsl_source should be non-empty and not have leading/trailing whitespace
        assert result["dsl_source"]
        assert result["dsl_source"] == result["dsl_source"].strip()


class TestExplainConst:
    def test_cgt_exempt_explanation(self) -> None:
        result = explain_rule(_rule("cgt_exempt"))
        assert "3,000" in result["explanation"]

    def test_pension_lsa_explanation(self) -> None:
        result = explain_rule(_rule("pension_lsa"))
        assert "268,275" in result["explanation"]

    def test_const_rule_has_no_variables(self) -> None:
        result = explain_rule(_rule("cgt_exempt"))
        assert result["variables"] == []


class TestExplainBandApply:
    def test_income_tax_bands_explanation_mentions_variable(self) -> None:
        result = explain_rule(_rule("income_tax_bands"))
        assert "taxable income" in result["explanation"].lower()

    def test_income_tax_bands_explanation_mentions_rates(self) -> None:
        result = explain_rule(_rule("income_tax_bands"))
        assert "20%" in result["explanation"]
        assert "40%" in result["explanation"]
        assert "45%" in result["explanation"]

    def test_income_tax_bands_has_one_variable(self) -> None:
        result = explain_rule(_rule("income_tax_bands"))
        assert result["variables"] == ["taxable_income"]


class TestExplainTaper:
    def test_pa_taper_explanation_mentions_threshold(self) -> None:
        result = explain_rule(_rule("pa_taper"))
        assert "100,000" in result["explanation"]

    def test_pa_taper_explanation_mentions_ratio(self) -> None:
        result = explain_rule(_rule("pa_taper"))
        assert "£1 for every £2" in result["explanation"]

    def test_pa_taper_has_one_variable(self) -> None:
        result = explain_rule(_rule("pa_taper"))
        assert result["variables"] == ["adjusted_net_income"]


class TestExplainIf:
    def test_cgt_rates_explanation_mentions_condition(self) -> None:
        result = explain_rule(_rule("cgt_rates"))
        assert "if" in result["explanation"].lower()
        assert "24" in result["explanation"]
        assert "18" in result["explanation"]

    def test_cgt_rates_has_one_variable(self) -> None:
        result = explain_rule(_rule("cgt_rates"))
        assert result["variables"] == ["is_higher_rate_taxpayer"]


class TestCollectVariables:
    def test_const_has_no_variables(self) -> None:
        assert _collect_variables({"node": "CONST", "value": 42}) == set()

    def test_var_returns_name(self) -> None:
        assert _collect_variables({"node": "VAR", "name": "income"}) == {"income"}

    def test_nested_variables(self) -> None:
        ast = {
            "node": "ADD",
            "args": [
                {"node": "VAR", "name": "a"},
                {"node": "VAR", "name": "b"},
            ],
        }
        assert _collect_variables(ast) == {"a", "b"}

    def test_deduplicates_variables(self) -> None:
        ast = {
            "node": "ADD",
            "args": [
                {"node": "VAR", "name": "x"},
                {"node": "VAR", "name": "x"},
            ],
        }
        assert _collect_variables(ast) == {"x"}
