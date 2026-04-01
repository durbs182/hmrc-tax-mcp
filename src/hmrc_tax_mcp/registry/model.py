"""Rule registry data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Citation(BaseModel):
    label: str
    url: str


class RuleEntry(BaseModel):
    """A single versioned, immutable tax rule entry in the registry."""

    rule_id: str
    version: str
    tax_year: str
    jurisdiction: str  # "rUK" | "scotland" | ...
    title: str
    description: str
    dsl_source: str
    ast: dict[str, Any]
    checksum: str  # SHA-256 of canonical AST (without metadata)
    citations: list[Citation]
    provenance: str  # "manual" | "nl_extracted" | "migrated"
    published_at: datetime
    reviewed_by: str | None = None
    monetary_output: bool = False  # True if this rule produces a sterling monetary amount
