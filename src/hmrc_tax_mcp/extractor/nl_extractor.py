"""
Natural Language Extractor (stub).

Converts HMRC prose → DSL using an LLM, with a mandatory human review gate.
Full implementation in a later phase.
"""

from __future__ import annotations


class NLExtractor:
    """LLM-assisted HMRC prose → DSL extractor. Requires human review before publication."""

    def extract(self, hmrc_text: str) -> str:
        raise NotImplementedError("NL extractor not yet implemented")
