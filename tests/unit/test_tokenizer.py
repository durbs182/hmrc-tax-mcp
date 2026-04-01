"""Unit tests for the DSL tokenizer."""

from __future__ import annotations

import pytest

from hmrc_tax_mcp.dsl.tokenizer import Token, TokenizeError, tokenize


class TestNumbers:
    def test_integer(self) -> None:
        tokens = tokenize("12570")
        assert tokens == [Token("NUMBER", "12570", 1, 1)]

    def test_float(self) -> None:
        tokens = tokenize("0.45")
        assert tokens == [Token("NUMBER", "0.45", 1, 1)]

    def test_multiple_numbers(self) -> None:
        tokens = tokenize("100 200")
        assert [t.value for t in tokens] == ["100", "200"]


class TestIdents:
    def test_simple_ident(self) -> None:
        tokens = tokenize("income")
        assert tokens == [Token("IDENT", "income", 1, 1)]

    def test_underscore_ident(self) -> None:
        tokens = tokenize("adjusted_net_income")
        assert tokens[0].value == "adjusted_net_income"

    def test_keyword_is_ident_kind(self) -> None:
        # Keywords are returned as IDENT tokens; parser handles them by value
        tokens = tokenize("let return bands taper")
        assert all(t.kind == "IDENT" for t in tokens)
        assert [t.value for t in tokens] == ["let", "return", "bands", "taper"]


class TestOperators:
    def test_comparison_ops(self) -> None:
        tokens = tokenize(">= <= == !=")
        assert [t.value for t in tokens] == [">=", "<=", "==", "!="]

    def test_arithmetic_ops(self) -> None:
        tokens = tokenize("+ - * /")
        assert [t.kind for t in tokens] == ["OP", "OP", "OP", "OP"]


class TestPunctuation:
    def test_punct(self) -> None:
        tokens = tokenize("(a, b)")
        kinds = [t.kind for t in tokens]
        assert "PUNCT" in kinds


class TestNewlines:
    def test_newline_emitted(self) -> None:
        tokens = tokenize("a\nb")
        kinds = [t.kind for t in tokens]
        assert "NEWLINE" in kinds

    def test_consecutive_newlines_collapsed(self) -> None:
        tokens = tokenize("a\n\n\nb")
        nl_count = sum(1 for t in tokens if t.kind == "NEWLINE")
        assert nl_count == 1


class TestComments:
    def test_comment_stripped(self) -> None:
        tokens = tokenize("income # this is a comment")
        assert all(t.kind != "COMMENT" for t in tokens)
        assert tokens[0].value == "income"


class TestErrors:
    def test_unexpected_char_raises(self) -> None:
        with pytest.raises(TokenizeError, match="Unexpected character"):
            tokenize("income @ 100")


class TestStrings:
    def test_string_literal(self) -> None:
        tokens = tokenize('"hello world"')
        assert tokens[0].kind == "STRING"
        assert tokens[0].value == '"hello world"'
