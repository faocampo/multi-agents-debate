from __future__ import annotations

import json
from dataclasses import dataclass

from app.client import ProviderTimeout
from app.models import LLMModelInfo
from app.prompts import (
    ADVOCATE_SYSTEM,
    CLARIFYING_QUESTIONS_SYSTEM,
    DEBATE_SYSTEM,
    EXPERT_SYSTEM,
    ROLE_PLANNER_SYSTEM,
    SYNTHESIS_SYSTEM,
)

ROLES = [
    {"name": "Customer Advocate", "focus": "Adoption", "bias": "Prefer usability"},
    {"name": "Finance Lead", "focus": "Economics", "bias": "Protect runway"},
    {"name": "Engineer", "focus": "Delivery risk", "bias": "Prefer reversible systems"},
]


@dataclass(slots=True)
class CapturedCall:
    system: str
    user: str
    temperature: float
    model: str | None = None


class ScriptedClient:
    def __init__(self, fail_system: str | None = None) -> None:
        self.calls: list[CapturedCall] = []
        self.fail_system = fail_system

    async def complete(
        self, system: str, user: str, temperature: float, model: str | None = None
    ) -> str:
        self.calls.append(CapturedCall(system, user, temperature, model))
        if self.fail_system is not None and system == self.fail_system:
            raise ProviderTimeout("scripted timeout")
        payload = json.loads(user)
        if system == CLARIFYING_QUESTIONS_SYSTEM:
            return json.dumps(["What outcome matters most?", "Who is affected?"])
        if system.startswith(ROLE_PLANNER_SYSTEM):
            return json.dumps(ROLES)
        if system == EXPERT_SYSTEM:
            return f"## Recommendation\n\nInitial analysis from {payload['role']['name']}."
        if system == DEBATE_SYSTEM:
            return f"## Revised recommendation\n\nRebuttal from {payload['role']['name']}."
        if system == ADVOCATE_SYSTEM:
            return "## Shared assumptions under attack\n\nThe plan assumes stable demand."
        if system == SYNTHESIS_SYSTEM:
            return "## Verdict\n\nRun a reversible pilot."
        raise AssertionError("Unexpected system prompt")

    async def list_models(self, zdr: bool = False) -> list[LLMModelInfo]:
        models = [
            LLMModelInfo(id="openai/gpt-4o-mini", name="GPT-4o Mini"),
            LLMModelInfo(id="test/test-model", name="Test Model"),
        ]
        if zdr:
            return [LLMModelInfo(id="openai/gpt-4o-mini", name="GPT-4o Mini")]
        return models
