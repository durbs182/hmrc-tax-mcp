"""Unit tests for AST canonicalisation and SHA-256 hashing."""

from __future__ import annotations

from hmrc_tax_mcp.ast.canonical import ast_checksum, canonicalise, sha256_hash


SIMPLE_AST = {"node": "CONST", "value": 12570}

TAPER_AST = {
    "node": "TAPER",
    "args": [{"node": "VAR", "name": "adjusted_net_income"}],
    "threshold": {"node": "CONST", "value": 100000},
    "ratio": {"node": "CONST", "value": 0.5},
    "base": {"node": "CONST", "value": 12570},
}


class TestCanonicalise:
    def test_produces_compact_json(self) -> None:
        result = canonicalise(SIMPLE_AST)
        assert " " not in result
        assert "\n" not in result

    def test_keys_sorted(self) -> None:
        # node before value (n < v)
        result = canonicalise(SIMPLE_AST)
        assert result.index('"node"') < result.index('"value"')

    def test_metadata_stripped_by_default(self) -> None:
        ast_with_meta = {"node": "CONST", "value": 12570, "metadata": {"source": "test"}}
        assert canonicalise(ast_with_meta) == canonicalise(SIMPLE_AST)

    def test_metadata_included_when_requested(self) -> None:
        ast_with_meta = {"node": "CONST", "value": 12570, "metadata": {"source": "test"}}
        with_meta = canonicalise(ast_with_meta, include_metadata=True)
        without_meta = canonicalise(SIMPLE_AST, include_metadata=False)
        assert with_meta != without_meta

    def test_none_values_stripped(self) -> None:
        ast_with_none = {"node": "CONST", "value": 12570, "metadata": None}
        result = canonicalise(ast_with_none)
        assert "null" not in result

    def test_stable_across_calls(self) -> None:
        assert canonicalise(TAPER_AST) == canonicalise(TAPER_AST)


class TestSha256Hash:
    def test_produces_64_char_hex(self) -> None:
        result = sha256_hash(canonicalise(SIMPLE_AST))
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_hash(self) -> None:
        h1 = sha256_hash(canonicalise(SIMPLE_AST))
        h2 = sha256_hash(canonicalise(SIMPLE_AST))
        assert h1 == h2

    def test_different_ast_different_hash(self) -> None:
        h1 = sha256_hash(canonicalise({"node": "CONST", "value": 12570}))
        h2 = sha256_hash(canonicalise({"node": "CONST", "value": 12571}))
        assert h1 != h2


class TestAstChecksum:
    def test_returns_hex_string(self) -> None:
        result = ast_checksum(SIMPLE_AST)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_metadata_does_not_affect_checksum(self) -> None:
        a = ast_checksum({"node": "CONST", "value": 12570})
        b = ast_checksum({"node": "CONST", "value": 12570, "metadata": {"x": 1}})
        assert a == b
