"""
DSL tokenizer for the HMRC tax rule language.

Converts raw DSL text into a flat stream of tokens.

Token kinds:
  NUMBER  — integer or decimal literal (e.g. 12570, 0.45)
  STRING  — double-quoted string literal
  IDENT   — identifier or keyword (e.g. income, let, bands)
  OP      — operator (==, !=, >=, <=, >, <, +, -, *, /)
  PUNCT   — punctuation (, : %)
  NEWLINE — significant line break (used by bands/taper blocks)

Keywords (returned as IDENT with value matched by parser):
  let return bands taper threshold ratio base per at to and or not
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KEYWORDS = frozenset({
    "let", "return", "bands", "taper",
    "threshold", "ratio", "base", "per", "at", "to",
    "and", "or", "not", "true", "false",
})

_TOKEN_SPEC = [
    ("NUMBER",   r"\d+(?:\.\d+)?"),
    ("STRING",   r'"[^"]*"'),
    ("OP",       r"==|!=|>=|<=|>|<|\+|-|\*|/|="),
    ("PUNCT",    r"[(),:+%]"),
    ("IDENT",    r"[A-Za-z_][A-Za-z0-9_]*"),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
    ("COMMENT",  r"#[^\n]*"),
    ("MISMATCH", r"."),
]

_TOKEN_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC)
)


@dataclass(frozen=True)
class Token:
    kind: str   # NUMBER | STRING | IDENT | OP | PUNCT | NEWLINE
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


class TokenizeError(Exception):
    pass


def tokenize(text: str) -> list[Token]:
    """
    Tokenize DSL text into a list of Tokens.

    Raises TokenizeError on unexpected characters.
    Strips SKIP and COMMENT tokens; collapses consecutive NEWLINEs.
    """
    tokens: list[Token] = []
    line = 1
    line_start = 0

    for m in _TOKEN_RE.finditer(text):
        kind = m.lastgroup
        value = m.group()
        col = m.start() - line_start + 1

        if kind == "SKIP" or kind == "COMMENT":
            continue

        if kind == "MISMATCH":
            raise TokenizeError(
                f"Unexpected character {value!r} at line {line}, col {col}"
            )

        if kind == "NEWLINE":
            # Collapse consecutive newlines; track line number
            if tokens and tokens[-1].kind != "NEWLINE":
                tokens.append(Token("NEWLINE", "\n", line, col))
            line += 1
            line_start = m.end()
            continue

        if kind is None:
            continue
        tokens.append(Token(kind, value, line, col))

    return tokens
