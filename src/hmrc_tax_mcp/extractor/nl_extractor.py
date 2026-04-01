"""
Natural Language Extractor.

Converts HMRC prose → a draft DSL string using Anthropic Claude.
The output is ALWAYS flagged as unreviewed — it must pass human review
before being committed to the rule registry.

Requires: pip install hmrc-tax-mcp[extractor]
"""

from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass, field
from typing import Optional

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert UK tax engineer. Your task is to convert HMRC legislative
    prose into a deterministic, auditable DSL rule.

    DSL syntax reference:

        # Constant value
        return <number>

        # Arithmetic / conditional
        let x = <expr>
        return <expr>

        # if/then/else (single-line expression)
        return if <cond> then <expr> else <expr>

        # Tax bands (BAND_APPLY node)
        bands <variable>:
          <lower> to <upper> at <rate>%
          <lower>+ at <rate>%

        # Taper (TAPER node)
        taper <variable>:
          threshold <number>
          ratio 1 per 2
          base <number>

    Rules:
    - Use only Decimal-safe literals (no floating point).
    - Variable names must be snake_case.
    - Do NOT invent values — only use values from the provided text.
    - Return ONLY the DSL source, no surrounding explanation or markdown fences.

    After the DSL, output a JSON block delimited by <<<JSON and JSON>>> containing:
    {
      "rule_id": "<snake_case>",
      "title": "<short human title>",
      "description": "<one sentence>",
      "tax_year": "2025-26",
      "jurisdiction": "rUK",
      "citations": [{"title": "...", "url": "...", "section": "..."}]
    }
""")


@dataclass
class ExtractionResult:
    """Result of an NL extraction attempt. Always requires human review before publication."""

    dsl_source: str
    rule_id: str
    title: str
    description: str
    tax_year: str
    jurisdiction: str
    citations: list[dict]
    raw_response: str
    reviewed_by: Optional[str] = None  # Always None until a human signs off
    review_notes: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def requires_review(self) -> bool:
        """Always True — LLM output must never be published without human review."""
        return self.reviewed_by is None

    def to_registry_dict(self) -> dict:
        """
        Produce a registry-compatible dict. The caller must compile the DSL
        and compute the checksum before writing to YAML.
        """
        return {
            "rule_id": self.rule_id,
            "version": "draft-0",
            "title": self.title,
            "description": self.description,
            "tax_year": self.tax_year,
            "jurisdiction": self.jurisdiction,
            "dsl_source": self.dsl_source,
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
            "citations": self.citations,
            "provenance": {
                "source": "nl_extractor",
                "model": "claude-3-5-haiku-20241022",
                "status": "DRAFT — awaiting human review",
            },
        }


class NLExtractor:
    """
    LLM-assisted HMRC prose → DSL extractor.

    Requires the ``anthropic`` package (install with ``pip install hmrc-tax-mcp[extractor]``).
    The ANTHROPIC_API_KEY environment variable must be set.

    All results are marked ``reviewed_by: null`` — publication is blocked until
    a human engineer validates the output against the original HMRC source.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def _client(self):  # type: ignore[return]
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for NLExtractor. "
                "Install it with: pip install hmrc-tax-mcp[extractor]"
            ) from exc
        return anthropic.Anthropic(api_key=self._api_key)

    def extract(self, hmrc_text: str) -> ExtractionResult:
        """
        Send HMRC prose to Claude and parse the returned DSL + metadata.

        Returns an ExtractionResult with reviewed_by=None. The result must be
        reviewed by a human before it can be added to the rule registry.
        """
        client = self._client()
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Convert the following HMRC text to DSL:\n\n"
                        f"{hmrc_text.strip()}"
                    ),
                }
            ],
        )
        raw = message.content[0].text
        return _parse_response(raw)


def _parse_response(raw: str) -> ExtractionResult:
    """Parse the LLM response into an ExtractionResult."""
    warnings: list[str] = []

    # Split on the JSON delimiter
    if "<<<JSON" in raw and "JSON>>>" in raw:
        dsl_part, _, rest = raw.partition("<<<JSON")
        json_part, _, _ = rest.partition("JSON>>>")
        dsl_source = dsl_part.strip()
        try:
            meta = json.loads(json_part.strip())
        except json.JSONDecodeError as exc:
            warnings.append(f"JSON parse error: {exc}")
            meta = {}
    else:
        # Fallback: treat entire response as DSL, no metadata
        dsl_source = raw.strip()
        meta = {}
        warnings.append("No JSON metadata block found in response — metadata fields are empty.")

    # Strip markdown fences if the model ignored the instruction
    if dsl_source.startswith("```"):
        lines = dsl_source.splitlines()
        dsl_source = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()
        warnings.append("Markdown code fence stripped from DSL output.")

    return ExtractionResult(
        dsl_source=dsl_source,
        rule_id=meta.get("rule_id", "unknown_rule"),
        title=meta.get("title", ""),
        description=meta.get("description", ""),
        tax_year=meta.get("tax_year", ""),
        jurisdiction=meta.get("jurisdiction", ""),
        citations=meta.get("citations", []),
        raw_response=raw,
        warnings=warnings,
    )
