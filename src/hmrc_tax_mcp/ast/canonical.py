"""
Canonical JSON serialisation and SHA-256 hashing for AST nodes.

Rules:
- Keys sorted lexicographically
- No extra whitespace
- Metadata excluded from structural checksums
- None-valued keys stripped before hashing
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _sort_keys_deep(obj: Any) -> Any:
    """Recursively sort dict keys for canonical representation."""
    if isinstance(obj, dict):
        return {k: _sort_keys_deep(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_keys_deep(item) for item in obj]
    return obj


def _strip_none(obj: Any) -> Any:
    """Remove None-valued keys from dicts."""
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(item) for item in obj]
    return obj


def _strip_metadata(obj: Any) -> Any:
    """Recursively remove 'metadata' keys so the checksum reflects structure only."""
    if isinstance(obj, dict):
        return {k: _strip_metadata(v) for k, v in obj.items() if k != "metadata"}
    if isinstance(obj, list):
        return [_strip_metadata(item) for item in obj]
    return obj


def canonicalise(ast_dict: dict[str, Any], include_metadata: bool = False) -> str:
    """
    Produce a canonical JSON string from an AST dict.

    Args:
        ast_dict: Raw AST as a dict (e.g. from model.model_dump()).
        include_metadata: If False (default), metadata fields are stripped so
                          the hash reflects only structural content.

    Returns:
        Compact, sorted-key JSON string suitable for hashing.
    """
    data = _strip_none(_sort_keys_deep(ast_dict))
    if not include_metadata:
        data = _strip_metadata(data)
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


def sha256_hash(canonical_json: str) -> str:
    """Return the SHA-256 hex digest of a canonical JSON string."""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def ast_checksum(ast_dict: dict[str, Any]) -> str:
    """Canonicalise (without metadata) and return SHA-256 hex digest."""
    return sha256_hash(canonicalise(ast_dict, include_metadata=False))
