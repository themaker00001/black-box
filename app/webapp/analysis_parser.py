from __future__ import annotations

import re

from pydantic import BaseModel, Field

_SECTION_RE = re.compile(r"##\s*(.+?)\s*\n(.*?)(?=\n##|\Z)", re.DOTALL)
_BULLET_RE = re.compile(r"^\s*-\s+(.*)$", re.MULTILINE)


class AnalysisSections(BaseModel):
    most_likely_cause: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    alternative_explanations: str = ""
    next_steps: list[str] = Field(default_factory=list)


def parse_analysis(text: str) -> AnalysisSections:
    """Splits the agent's markdown response into its named sections so the UI
    can render distinct cards instead of one undifferentiated block of text.
    Falls back gracefully to putting everything under 'most_likely_cause' if
    the model didn't follow the expected structure."""
    sections: dict[str, str] = {}
    for match in _SECTION_RE.finditer(text or ""):
        heading = match.group(1).strip().lower()
        body = match.group(2).strip()
        sections[heading] = body

    if not sections:
        return AnalysisSections(most_likely_cause=text.strip())

    return AnalysisSections(
        most_likely_cause=sections.get("most likely cause", "").strip(),
        supporting_evidence=_BULLET_RE.findall(sections.get("supporting evidence", "")),
        alternative_explanations=sections.get("alternative explanations", "").strip(),
        next_steps=_BULLET_RE.findall(sections.get("suggested next steps", "")),
    )
