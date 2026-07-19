"""Orchestration for conflict-driven multi-agent expert analysis."""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, TypeVar

from .client import ChatClient
from .models import AnalysisResult, ExpertOpinion, ExpertRole, SwarmConfig
from .prompts import (
    DEBATE_SYSTEM,
    DEVIL_SYSTEM,
    EXPERT_SYSTEM,
    MERGE_SYSTEM,
    ORCHESTRATOR_SYSTEM,
)


class SwarmError(RuntimeError):
    """Base error for the analysis pipeline."""


class RolePlanningError(SwarmError):
    """Raised when the orchestrator does not return valid expert roles."""


class StageExecutionError(SwarmError):
    """Raised when an expert or debate worker fails."""

    def __init__(self, stage: str, subject: str) -> None:
        super().__init__("{} failed for {}".format(stage, subject))
        self.stage = stage
        self.subject = subject


T = TypeVar("T")
R = TypeVar("R")


class MultiAgentAnalyzer:
    """Run role planning, independent analysis, debate, attack, and merge.

    A custom client only needs to implement ``complete(system, user,
    temperature)``. Because expert stages run concurrently, custom clients
    should be safe to call from multiple threads.
    """

    def __init__(self, client: ChatClient, config: Optional[SwarmConfig] = None) -> None:
        self.client = client
        self.config = config or SwarmConfig()

    def analyze(self, task: str, debate: Optional[bool] = None) -> AnalysisResult:
        """Run the full pipeline for one decision or analytical question."""

        task = task.strip()
        if not task:
            raise ValueError("task cannot be empty")

        roles = self.plan_roles(task)
        opinions = self.run_independent_experts(roles, task)
        debate_used = self.config.include_debate if debate is None else debate
        if debate_used:
            opinions = self.run_debate_round(opinions, task)

        devils_advocate = self.run_devils_advocate(opinions, task)
        synthesis = self.merge_opinions(opinions, devils_advocate, task)
        return AnalysisResult(
            task=task,
            roles=roles,
            opinions=opinions,
            devils_advocate=devils_advocate,
            synthesis=synthesis,
            debate_used=debate_used,
        )

    def plan_roles(self, task: str) -> List[ExpertRole]:
        """Dynamically choose conflicting roles for this particular task."""

        system = ORCHESTRATOR_SYSTEM.format(
            min_roles=self.config.min_roles,
            max_roles=self.config.max_roles,
        )
        raw = self.client.complete(system, "Decision to analyze:\n{}".format(task), self.config.role_temperature)
        payload = self._extract_json_array(raw)
        if not self.config.min_roles <= len(payload) <= self.config.max_roles:
            raise RolePlanningError(
                "orchestrator returned {} roles; expected {}-{}".format(
                    len(payload), self.config.min_roles, self.config.max_roles
                )
            )

        roles: List[ExpertRole] = []
        seen_names = set()
        for index, item in enumerate(payload):
            if not isinstance(item, Mapping):
                raise RolePlanningError("role {} is not an object".format(index + 1))
            values: Dict[str, str] = {}
            for key in ("name", "focus", "bias"):
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise RolePlanningError(
                        "role {} has an invalid {}".format(index + 1, key)
                    )
                values[key] = value.strip()
            normalized_name = values["name"].casefold()
            if normalized_name in seen_names:
                raise RolePlanningError("orchestrator returned duplicate role names")
            seen_names.add(normalized_name)
            roles.append(ExpertRole(**values))
        return roles

    def run_independent_experts(
        self, roles: Sequence[ExpertRole], task: str
    ) -> List[ExpertOpinion]:
        """Run the first round concurrently without cross-expert context."""

        def analyze_role(role: ExpertRole) -> ExpertOpinion:
            system = EXPERT_SYSTEM.format(
                name=role.name,
                focus=role.focus,
                bias=role.bias,
            )
            answer = self.client.complete(
                system,
                "Decision to analyze:\n{}".format(task),
                self.config.expert_temperature,
            )
            return ExpertOpinion(role=role, initial_analysis=answer.strip())

        return self._parallel_map(
            stage="independent expert analysis",
            items=roles,
            worker=analyze_role,
            label=lambda role: role.name,
        )

    def run_debate_round(
        self, opinions: Sequence[ExpertOpinion], task: str
    ) -> List[ExpertOpinion]:
        """Let each expert independently rebut every other first-round view."""

        def rebut(opinion: ExpertOpinion) -> ExpertOpinion:
            opponents = "\n\n".join(
                "### {}\n{}".format(other.role.name, other.current_analysis)
                for other in opinions
                if other.role.name != opinion.role.name
            )
            system = DEBATE_SYSTEM.format(
                name=opinion.role.name,
                focus=opinion.role.focus,
                bias=opinion.role.bias,
                own_opinion=opinion.current_analysis,
            )
            user = "Decision:\n{}\n\nOpposing expert positions:\n{}".format(task, opponents)
            response = self.client.complete(system, user, self.config.debate_temperature)
            return replace(opinion, debate_response=response.strip())

        return self._parallel_map(
            stage="debate round",
            items=opinions,
            worker=rebut,
            label=lambda opinion: opinion.role.name,
        )

    def run_devils_advocate(
        self, opinions: Sequence[ExpertOpinion], task: str
    ) -> str:
        """Attack the swarm's apparent consensus before synthesis."""

        user = "Decision:\n{}\n\nCurrent expert positions:\n{}".format(
            task, self._opinion_block(opinions)
        )
        return self.client.complete(
            DEVIL_SYSTEM, user, self.config.devil_temperature
        ).strip()

    def merge_opinions(
        self,
        opinions: Sequence[ExpertOpinion],
        devils_advocate: str,
        task: str,
    ) -> str:
        """Synthesize the result while retaining conflicts and minority risks."""

        user = (
            "Decision:\n{task}\n\nExpert positions:\n{opinions}\n\n"
            "Devil's advocate critique:\n{devil}"
        ).format(
            task=task,
            opinions=self._opinion_block(opinions),
            devil=devils_advocate,
        )
        return self.client.complete(
            MERGE_SYSTEM, user, self.config.merge_temperature
        ).strip()

    def _parallel_map(
        self,
        stage: str,
        items: Sequence[T],
        worker: Callable[[T], R],
        label: Callable[[T], str],
    ) -> List[R]:
        if not items:
            return []
        worker_count = min(len(items), self.config.max_workers)
        ordered: List[Optional[R]] = [None] * len(items)
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            future_map: Dict[Future[R], Tuple[int, T]] = {
                pool.submit(worker, item): (index, item)
                for index, item in enumerate(items)
            }
            for future in as_completed(future_map):
                index, item = future_map[future]
                try:
                    ordered[index] = future.result()
                except Exception as exc:
                    for pending in future_map:
                        pending.cancel()
                    raise StageExecutionError(stage, label(item)) from exc
        return [result for result in ordered if result is not None]

    @staticmethod
    def _extract_json_array(raw: str) -> List[Any]:
        decoder = json.JSONDecoder()
        for index, character in enumerate(raw):
            if character != "[":
                continue
            try:
                value, _ = decoder.raw_decode(raw[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, list):
                return value
        raise RolePlanningError("orchestrator response did not contain a JSON array")

    @staticmethod
    def _opinion_block(opinions: Sequence[ExpertOpinion]) -> str:
        return "\n\n".join(
            "### {}\n{}".format(opinion.role.name, opinion.current_analysis)
            for opinion in opinions
        )

