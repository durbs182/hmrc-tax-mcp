"""
Recursive-descent parser for the HMRC DSL.

Implements the grammar from the technical specification (mcp.md §5.4):

  program      = statement* EOF
  statement    = let_stmt | return_stmt | expr_stmt
  let_stmt     = "let" IDENT "=" expr NEWLINE
  return_stmt  = "return" expr NEWLINE?
  expr_stmt    = expr NEWLINE

  expr         = logic_or
  logic_or     = logic_and ("or" logic_and)*
  logic_and    = equality ("and" equality)*
  equality     = comparison (("==" | "!=") comparison)*
  comparison   = term ((">" | ">=" | "<" | "<=") term)*
  term         = factor (("+" | "-") factor)*
  factor       = unary (("*" | "/") unary)*
  unary        = "not" unary | primary

  primary      = NUMBER | STRING | "true" | "false"
               | IDENT "(" arg_list? ")"   -- function call
               | IDENT                     -- variable
               | "(" expr ")"
               | bands_expr
               | taper_expr

  bands_expr   = "bands" IDENT ":" NEWLINE band_line+
  band_line    = NUMBER "to" NUMBER "at" NUMBER "%"? NEWLINE
               | NUMBER "+" "at" NUMBER "%"? NEWLINE

  taper_expr   = "taper" IDENT ":" NEWLINE taper_line+
  taper_line   = ("threshold" | "ratio" | "base") NUMBER NEWLINE
               | "ratio" NUMBER "per" NUMBER NEWLINE

Parse result is a list of statement dicts (proto-AST), which the compiler
then converts to the canonical ASTNode format.
"""

from __future__ import annotations

from typing import Any

from hmrc_tax_mcp.dsl.tokenizer import Token, tokenize


class ParseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _peek(self) -> Token | None:
        # Skip any leading newlines when peeking for statement starts
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _peek_non_nl(self) -> Token | None:
        pos = self._pos
        while pos < len(self._tokens) and self._tokens[pos].kind == "NEWLINE":
            pos += 1
        return self._tokens[pos] if pos < len(self._tokens) else None

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _match(self, kind: str, value: str | None = None) -> Token | None:
        tok = self._peek()
        if tok is None:
            return None
        if tok.kind != kind:
            return None
        if value is not None and tok.value != value:
            return None
        self._pos += 1
        return tok

    def _expect(self, kind: str, value: str | None = None) -> Token:
        tok = self._match(kind, value)
        if tok is None:
            got = self._peek()
            desc = f"{kind}({value!r})" if value else kind
            got_desc = repr(got) if got else "EOF"
            raise ParseError(f"Expected {desc}, got {got_desc}")
        return tok

    def _skip_newlines(self) -> None:
        while self._peek() and self._peek().kind == "NEWLINE":  # type: ignore[union-attr]
            self._advance()

    # ------------------------------------------------------------------
    # Program
    # ------------------------------------------------------------------

    def parse_program(self) -> list[dict[str, Any]]:
        stmts: list[dict[str, Any]] = []
        self._skip_newlines()
        while self._peek() is not None:
            stmts.append(self._parse_statement())
            self._skip_newlines()
        return stmts

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _parse_statement(self) -> dict[str, Any]:
        tok = self._peek()
        if tok is None:
            raise ParseError("Unexpected end of input")

        if tok.kind == "IDENT" and tok.value == "let":
            return self._parse_let()

        if tok.kind == "IDENT" and tok.value == "return":
            return self._parse_return()

        expr = self._parse_expr()
        self._match("NEWLINE")
        return {"stmt": "expr", "expr": expr}

    def _parse_let(self) -> dict[str, Any]:
        self._expect("IDENT", "let")
        name = self._expect("IDENT")
        self._expect("OP", "=")
        expr = self._parse_expr()
        self._match("NEWLINE")
        return {"stmt": "let", "name": name.value, "expr": expr}

    def _parse_return(self) -> dict[str, Any]:
        self._expect("IDENT", "return")
        expr = self._parse_expr()
        self._match("NEWLINE")
        return {"stmt": "return", "expr": expr}

    # ------------------------------------------------------------------
    # Expressions (precedence climbing via recursive descent)
    # ------------------------------------------------------------------

    def _parse_expr(self) -> dict[str, Any]:
        return self._parse_logic_or()

    def _parse_logic_or(self) -> dict[str, Any]:
        left = self._parse_logic_and()
        while self._peek() and self._peek().kind == "IDENT" and self._peek().value == "or":  # type: ignore[union-attr]
            self._advance()
            right = self._parse_logic_and()
            left = {"node": "OR", "args": [left, right]}
        return left

    def _parse_logic_and(self) -> dict[str, Any]:
        left = self._parse_equality()
        while self._peek() and self._peek().kind == "IDENT" and self._peek().value == "and":  # type: ignore[union-attr]
            self._advance()
            right = self._parse_equality()
            left = {"node": "AND", "args": [left, right]}
        return left

    def _parse_equality(self) -> dict[str, Any]:
        left = self._parse_comparison()
        while self._peek() and self._peek().kind == "OP" and self._peek().value in ("==", "!="):  # type: ignore[union-attr]
            op = self._advance().value
            right = self._parse_comparison()
            left = {"node": "EQ" if op == "==" else "NEQ", "args": [left, right]}
        return left

    def _parse_comparison(self) -> dict[str, Any]:
        left = self._parse_term()
        _ops = {">": "GT", "<": "LT", ">=": "GTE", "<=": "LTE"}
        while self._peek() and self._peek().kind == "OP" and self._peek().value in _ops:  # type: ignore[union-attr]
            op = self._advance().value
            right = self._parse_term()
            left = {"node": _ops[op], "args": [left, right]}
        return left

    def _parse_term(self) -> dict[str, Any]:
        left = self._parse_factor()
        while self._peek() and self._peek().kind == "OP" and self._peek().value in ("+", "-"):  # type: ignore[union-attr]
            op = self._advance().value
            right = self._parse_factor()
            left = {"node": "ADD" if op == "+" else "SUB", "args": [left, right]}
        return left

    def _parse_factor(self) -> dict[str, Any]:
        left = self._parse_unary()
        while self._peek() and self._peek().kind == "OP" and self._peek().value in ("*", "/"):  # type: ignore[union-attr]
            op = self._advance().value
            right = self._parse_unary()
            left = {"node": "MUL" if op == "*" else "DIV", "args": [left, right]}
        return left

    def _parse_unary(self) -> dict[str, Any]:
        if self._peek() and self._peek().kind == "IDENT" and self._peek().value == "not":  # type: ignore[union-attr]
            self._advance()
            return {"node": "NOT", "args": [self._parse_unary()]}
        return self._parse_primary()

    def _parse_primary(self) -> dict[str, Any]:
        tok = self._peek()
        if tok is None:
            raise ParseError("Unexpected end of expression")

        # Number literal
        if tok.kind == "NUMBER":
            self._advance()
            v: int | float = int(tok.value) if "." not in tok.value else float(tok.value)
            return {"node": "CONST", "value": v}

        # String literal — not supported; the evaluator has no string type
        if tok.kind == "STRING":
            raise ParseError(
                f"String literals are not supported in this DSL (got {tok.value!r}). "
                "Only numeric and boolean constants are allowed."
            )

        # Parenthesised expression
        if tok.kind == "PUNCT" and tok.value == "(":
            self._advance()
            expr = self._parse_expr()
            self._expect("PUNCT", ")")
            return expr

        # Keyword-led constructs
        if tok.kind == "IDENT":
            if tok.value == "true":
                self._advance()
                return {"node": "CONST", "value": True}
            if tok.value == "false":
                self._advance()
                return {"node": "CONST", "value": False}
            if tok.value == "if":
                return self._parse_if()
            if tok.value == "bands":
                return self._parse_bands()
            if tok.value == "taper":
                return self._parse_taper()

            # Function call or variable reference
            self._advance()
            if self._peek() and self._peek().kind == "PUNCT" and self._peek().value == "(":  # type: ignore[union-attr]
                self._advance()  # consume "("
                args: list[dict[str, Any]] = []
                if not ((peek := self._peek()) and peek.kind == "PUNCT" and peek.value == ")"):
                    args.append(self._parse_expr())
                    while (peek := self._peek()) and peek.kind == "PUNCT" and peek.value == ",":
                        self._advance()
                        args.append(self._parse_expr())
                self._expect("PUNCT", ")")
                return {"node": "CALL", "name": tok.value, "args": args}

            return {"node": "VAR", "name": tok.value}

        raise ParseError(f"Unexpected token: {tok!r}")

    def _parse_if(self) -> dict[str, Any]:
        self._expect("IDENT", "if")
        condition = self._parse_expr()
        self._expect("IDENT", "then")
        then_expr = self._parse_expr()
        self._expect("IDENT", "else")
        else_expr = self._parse_expr()
        return {"node": "IF", "args": [condition, then_expr, else_expr]}

    # ------------------------------------------------------------------
    # bands_expr
    # ------------------------------------------------------------------

    def _parse_bands(self) -> dict[str, Any]:
        self._expect("IDENT", "bands")
        var_tok = self._expect("IDENT")
        self._expect("PUNCT", ":")
        self._expect("NEWLINE")

        bands: list[dict[str, Any]] = []
        while True:
            # Must be indented (starts with a NUMBER)
            tok = self._peek()
            if tok is None or tok.kind != "NUMBER":
                break

            lower_tok = self._advance()
            lower = float(lower_tok.value) if "." in lower_tok.value else int(lower_tok.value)

            # Check for "NUMBER+" (open-ended upper band)
            if self._peek() and self._peek().kind == "OP" and self._peek().value == "+":  # type: ignore[union-attr]
                self._advance()  # consume "+"
                self._expect("IDENT", "at")
                rate_tok = self._expect("NUMBER")
                rate = float(rate_tok.value) / 100.0
                self._match("PUNCT", "%")  # optional explicit %
                self._match("NEWLINE")
                bands.append({"lower": lower, "upper": None, "rate": rate})
            else:
                self._expect("IDENT", "to")
                upper_tok = self._expect("NUMBER")
                upper = float(upper_tok.value) if "." in upper_tok.value else int(upper_tok.value)
                self._expect("IDENT", "at")
                rate_tok = self._expect("NUMBER")
                rate = float(rate_tok.value) / 100.0
                self._match("PUNCT", "%")  # optional explicit %
                self._match("NEWLINE")
                bands.append({"lower": lower, "upper": upper, "rate": rate})

        if not bands:
            raise ParseError("bands block must contain at least one band line")

        return {
            "node": "BAND_APPLY",
            "args": [{"node": "VAR", "name": var_tok.value}],
            "bands": bands,
        }

    # ------------------------------------------------------------------
    # taper_expr
    # ------------------------------------------------------------------

    def _parse_taper(self) -> dict[str, Any]:
        self._expect("IDENT", "taper")
        var_tok = self._expect("IDENT")
        self._expect("PUNCT", ":")
        self._expect("NEWLINE")

        threshold: dict[str, Any] | None = None
        ratio: dict[str, Any] | None = None
        base: dict[str, Any] | None = None

        while True:
            tok = self._peek()
            if (
                tok is None
                or tok.kind != "IDENT"
                or tok.value not in ("threshold", "ratio", "base")
            ):
                break
            key = self._advance().value

            if key == "ratio":
                num_tok = self._expect("NUMBER")
                num = float(num_tok.value) if "." in num_tok.value else int(num_tok.value)
                if self._peek() and self._peek().kind == "IDENT" and self._peek().value == "per":  # type: ignore[union-attr]
                    self._advance()  # consume "per"
                    denom_tok = self._expect("NUMBER")
                    denom = (
                        float(denom_tok.value) if "." in denom_tok.value else int(denom_tok.value)
                    )
                    ratio = {"node": "CONST", "value": num / denom}
                else:
                    ratio = {"node": "CONST", "value": num}
            else:
                val_tok = self._expect("NUMBER")
                val: int | float = (
                    int(val_tok.value) if "." not in val_tok.value else float(val_tok.value)
                )
                if key == "threshold":
                    threshold = {"node": "CONST", "value": val}
                else:
                    base = {"node": "CONST", "value": val}
            self._match("NEWLINE")

        if threshold is None or ratio is None or base is None:
            raise ParseError("taper block requires threshold, ratio, and base")

        return {
            "node": "TAPER",
            "args": [{"node": "VAR", "name": var_tok.value}],
            "threshold": threshold,
            "ratio": ratio,
            "base": base,
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(dsl_text: str) -> list[dict[str, Any]]:
    """
    Parse DSL text into a list of statement dicts.

    Args:
        dsl_text: Raw DSL source.

    Returns:
        List of statement dicts (proto-AST).

    Raises:
        TokenizeError: On invalid characters.
        ParseError: On invalid syntax.
    """
    tokens = tokenize(dsl_text)
    return Parser(tokens).parse_program()
