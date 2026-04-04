"""
Regenerate the citation map (manual_ref → rule_ids) by reading the citations
field from every rule YAML in the registry.

The map is written to scripts/indexing/citation_map.json and is consumed by
fetch_hmrc_sources.py when tagging chunks.

Usage:
    python tag_rules.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

RULES_DIR = Path("src/hmrc_tax_mcp/registry/rules")
OUTPUT = Path("scripts/indexing/citation_map.json")

# Pattern to extract a manual reference from a citation string or URL
# Matches: PTM063300, IHTM04261, CG64200, EIM01530, PIM1000, etc.
REF_PATTERN = re.compile(r"\b([A-Z]{2,6}\d{4,})\b")


def extract_refs(citation: dict | str) -> list[str]:
    """Extract manual section references from a citation dict or string."""
    if isinstance(citation, dict):
        text = f"{citation.get('label', '')} {citation.get('url', '')}"
    else:
        text = str(citation)
    return REF_PATTERN.findall(text.upper())


def build_citation_map() -> dict[str, list[str]]:
    """Return {manual_ref: [rule_id, ...]} by scanning all rule YAMLs."""
    citation_map: dict[str, set[str]] = {}

    # Scan one tax year only (all years have the same citations)
    year_dir = RULES_DIR / "2025-26"
    if not year_dir.exists():
        raise FileNotFoundError(f"Rules directory not found: {year_dir}")

    for yaml_path in year_dir.rglob("*.yaml"):
        data = yaml.safe_load(yaml_path.read_text())
        rule_id = data.get("rule_id")
        citations = data.get("citations", [])
        if not rule_id or not citations:
            continue

        for citation in citations:
            for ref in extract_refs(citation):
                citation_map.setdefault(ref, set()).add(rule_id)

    return {ref: sorted(rules) for ref, rules in sorted(citation_map.items())}


def main() -> None:
    mapping = build_citation_map()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
    print(f"Wrote {len(mapping)} citation mappings to {OUTPUT}")
    for ref, rules in list(mapping.items())[:10]:
        print(f"  {ref}: {rules}")
    if len(mapping) > 10:
        print(f"  … and {len(mapping) - 10} more")


if __name__ == "__main__":
    main()
