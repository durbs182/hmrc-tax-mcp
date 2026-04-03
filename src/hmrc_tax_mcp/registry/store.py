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


def _registry_key(rule_id: str, version: str, jurisdiction: str, tax_year: str) -> str:
    return f"{rule_id}@{version}@{jurisdiction}@{tax_year}"


def _semver_key(version: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple of ints (semver order)."""
    try:
        return tuple(int(x) for x in version.split("."))
    except ValueError:
        return (0,)


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
        key = _registry_key(entry.rule_id, entry.version, entry.jurisdiction, entry.tax_year)
        _registry[key] = entry
    _loaded = True


def get_rule(
    rule_id: str,
    version: str = "latest",
    jurisdiction: str | None = None,
    tax_year: str | None = None,
) -> RuleEntry | None:
    """
    Look up a rule by ID and version. 'latest' returns the highest semver version.

    When multiple jurisdictions publish the same rule_id (e.g. ``income_tax_bands``
    exists for both ``rUK`` and ``scotland``), pass ``jurisdiction`` to disambiguate.
    Omitting ``jurisdiction`` when multiple jurisdictions match raises ValueError
    to prevent accidentally returning the wrong jurisdiction's rule.

    When multiple tax years publish the same rule_id/version/jurisdiction,
    pass ``tax_year`` to select a specific year. For ``version='latest'``, ties
    are broken by returning the entry with the newest tax_year. For an explicit
    version, omitting ``tax_year`` when multiple years match raises ValueError.
    """
    if not _loaded:
        load_all_rules()

    if version != "latest":
        matches = [
            e for e in _registry.values()
            if e.rule_id == rule_id and e.version == version
            and (jurisdiction is None or e.jurisdiction == jurisdiction)
            and (tax_year is None or e.tax_year == tax_year)
        ]
        if jurisdiction is None and len(matches) > 1:
            ruk_matches = [e for e in matches if e.jurisdiction == "rUK"]
            matches = ruk_matches if ruk_matches else matches
        if tax_year is None and len(matches) > 1:
            tax_years = {e.tax_year for e in matches}
            if len(tax_years) > 1:
                raise ValueError(
                    f"Rule {rule_id!r} version {version!r} exists in multiple tax years "
                    f"({sorted(tax_years)}). Pass tax_year= to disambiguate."
                )
        return matches[0] if matches else None

    matches = [
        e for e in _registry.values()
        if e.rule_id == rule_id
        and (jurisdiction is None or e.jurisdiction == jurisdiction)
        and (tax_year is None or e.tax_year == tax_year)
    ]
    if not matches:
        return None

    # When multiple jurisdictions match and none was specified, default to rUK.
    # This prevents tools from failing when Copilot omits jurisdiction for
    # shared rules (e.g. income_tax_bands, pa_taper). Callers that need
    # Scottish rates should pass jurisdiction="scotland" explicitly.
    if jurisdiction is None:
        ambig_jurisdictions = {e.jurisdiction for e in matches}
        if len(ambig_jurisdictions) > 1:
            ruk_matches = [e for e in matches if e.jurisdiction == "rUK"]
            matches = ruk_matches if ruk_matches else matches

    # Sort by (semver, tax_year) so the newest year wins when versions tie.
    return sorted(matches, key=lambda e: (_semver_key(e.version), e.tax_year))[-1]


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
