"""
Rule registry store.

Loads rules from YAML files under registry/rules/<tax_year>/<jurisdiction>/.
Rules are immutable once loaded; updates create new versions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hmrc_tax_mcp.registry.model import RuleEntry

_registry: dict[str, RuleEntry] = {}
_loaded = False


def _rules_dir() -> Path:
    return Path(__file__).parent / "rules"


def load_all_rules() -> None:
    """Load all YAML rule files from the registry/rules directory tree."""
    global _loaded
    rules_dir = _rules_dir()
    for yaml_file in rules_dir.rglob("*.yaml"):
        with open(yaml_file) as f:
            data: Any = yaml.safe_load(f)
        if data is None:
            continue
        entry = RuleEntry.model_validate(data)
        key = f"{entry.rule_id}@{entry.version}"
        _registry[key] = entry
    _loaded = True


def get_rule(rule_id: str, version: str = "latest") -> RuleEntry | None:
    """Look up a rule by ID and version. 'latest' returns the highest semver string."""
    if not _loaded:
        load_all_rules()

    if version != "latest":
        return _registry.get(f"{rule_id}@{version}")

    matches = [e for e in _registry.values() if e.rule_id == rule_id]
    if not matches:
        return None
    return sorted(matches, key=lambda e: e.version)[-1]


def list_rules() -> list[RuleEntry]:
    """Return all registered rules sorted by rule_id then version."""
    if not _loaded:
        load_all_rules()
    return sorted(_registry.values(), key=lambda e: (e.rule_id, e.version))


def get_rule_snapshot(tax_year: str, jurisdiction: str) -> list[RuleEntry]:
    """Return all rules for a given tax year and jurisdiction."""
    if not _loaded:
        load_all_rules()
    return [
        e for e in _registry.values()
        if e.tax_year == tax_year and e.jurisdiction == jurisdiction
    ]
