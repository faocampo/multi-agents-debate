"""Data models used by the analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ExpertRole:
    """A deliberately opinionated lens chosen for a specific decision."""

    name: str
    focus: str
    bias: str

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "focus": self.focus, "bias": self.bias}


@dataclass(frozen=True)
class ExpertOpinion:
    """An expert's independent analysis and optional debate response."""

    role: ExpertRole
    initial_analysis: str
    debate_response: Optional[str] = None

    @property
    def current_analysis(self) -> str:
        """Return the strongest available position for downstream stages."""

        return self.debate_response or self.initial_analysis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.to_dict(),
            "initial_analysis": self.initial_analysis,
            "debate_response": self.debate_response,
            "current_analysis": self.current_analysis,
        }


@dataclass(frozen=True)
class SwarmConfig:
    """Controls role count, concurrency, and stage-specific creativity."""

    min_roles: int = 3
    max_roles: int = 5
    max_workers: int = 8
    include_debate: bool = True
    role_temperature: float = 0.9
    expert_temperature: float = 0.7
    debate_temperature: float = 0.6
    devil_temperature: float = 0.8
    merge_temperature: float = 0.4

    def __post_init__(self) -> None:
        if self.min_roles < 2:
            raise ValueError("min_roles must be at least 2")
        if self.max_roles < self.min_roles:
            raise ValueError("max_roles must be greater than or equal to min_roles")
        if self.max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        for name in (
            "role_temperature",
            "expert_temperature",
            "debate_temperature",
            "devil_temperature",
            "merge_temperature",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 2.0:
                raise ValueError("{} must be between 0 and 2".format(name))


@dataclass(frozen=True)
class AnalysisResult:
    """Complete, inspectable output of one swarm run."""

    task: str
    roles: List[ExpertRole] = field(default_factory=list)
    opinions: List[ExpertOpinion] = field(default_factory=list)
    devils_advocate: str = ""
    synthesis: str = ""
    debate_used: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "roles": [role.to_dict() for role in self.roles],
            "opinions": [opinion.to_dict() for opinion in self.opinions],
            "devils_advocate": self.devils_advocate,
            "synthesis": self.synthesis,
            "debate_used": self.debate_used,
        }

