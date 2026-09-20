from __future__ import annotations

import logging

from pydantic import BaseModel

from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from app.evidence.processor import EvidencePackage
from app.llm.interface import LlmClient, LlmError

logger = logging.getLogger(__name__)


class DebugAnalysis(BaseModel):
    incident_id: str
    model_used: str
    analysis_text: str
    succeeded: bool
    error: str | None = None


class DebugAgent:
    """The AI investigator: turns an EvidencePackage into a written analysis
    by asking the local LLM to correlate the evidence, name a likely cause,
    and suggest next steps — always citing the timeline it was given."""

    def __init__(self, llm: LlmClient, model_name: str) -> None:
        self._llm = llm
        self._model_name = model_name

    def investigate(self, evidence: EvidencePackage) -> DebugAnalysis:
        user_prompt = build_user_prompt(evidence)
        try:
            analysis_text = self._llm.complete(SYSTEM_PROMPT, user_prompt)
            return DebugAnalysis(
                incident_id=evidence.incident_id,
                model_used=self._model_name,
                analysis_text=analysis_text,
                succeeded=True,
            )
        except LlmError as exc:
            logger.error("debug agent could not reach the LLM: %s", exc)
            return DebugAnalysis(
                incident_id=evidence.incident_id,
                model_used=self._model_name,
                analysis_text=(
                    "AI analysis unavailable (local LLM could not be reached). "
                    "The raw evidence timeline and correlations below were still captured."
                ),
                succeeded=False,
                error=str(exc),
            )
