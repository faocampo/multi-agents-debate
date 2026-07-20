from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from uuid import UUID

from .client import (
    LLMClient,
    ProviderError,
    ProviderHTTPError,
    ProviderProtocolError,
    ProviderTimeout,
)
from .config import Settings
from .models import RoleLibrarySettings, RoleSpec, RunError, RunStage
from .prompts import (
    advocate_prompt,
    clarifying_questions_prompt,
    debate_prompt,
    expert_prompt,
    role_planner_prompt,
    synthesis_prompt,
)
from .role_parser import (
    MalformedClarification,
    MalformedRoles,
    parse_clarifying_questions,
    parse_roles,
)
from .role_store import RoleLibraryStore
from .store import RunStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CallResult:
    index: int
    output: str | None = None
    error: Exception | None = None


class RunExecutor:
    def __init__(
        self,
        store: RunStore,
        client: LLMClient,
        settings: Settings,
        *,
        heartbeat_interval: float = 15,
        role_library: RoleLibraryStore | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._settings = settings
        self._heartbeat_interval = heartbeat_interval
        self._role_library = role_library

    async def run(self, run_id: UUID) -> None:
        current_stage = RunStage.PLANNING_ROLES
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(run_id))
        try:
            record = await self._store.get_record(run_id)

            library_settings: RoleLibrarySettings | None = None
            if self._role_library is not None:
                try:
                    library_settings = await self._role_library.get_settings()
                except Exception:
                    logger.exception(
                        "failed to read role library settings; using environment defaults"
                    )
            active_model = (
                (library_settings.llm_model or self._settings.llm_model)
                if library_settings
                else self._settings.llm_model
            )
            desired_count = library_settings.default_role_count if library_settings else None
            clarification: list[tuple[str, str]] | None = None

            if record.clarify and not record.roles:
                current_stage = RunStage.AWAITING_CLARIFICATION
                await self._store.start_stage(run_id, current_stage)
                system, user = clarifying_questions_prompt(record.decision)
                raw_questions = await self._client.complete(
                    system,
                    user,
                    self._settings.llm_orchestrator_temperature,
                    model=active_model,
                )
                try:
                    questions = parse_clarifying_questions(raw_questions)
                except MalformedClarification:
                    logger.warning("clarification response was malformed; continuing without it")
                else:
                    await self._store.set_clarifying_questions(run_id, questions)
                    answers, skipped = await self._store.await_clarification(run_id)
                    if not skipped and answers is not None:
                        clarification = list(zip(questions, answers, strict=True))

            current_stage = RunStage.PLANNING_ROLES
            await self._store.start_stage(run_id, current_stage)
            if record.roles:
                roles = record.roles
                await self._store.set_roles(run_id, roles)
            else:
                system, user = role_planner_prompt(
                    record.decision,
                    desired_role_count=desired_count,
                    clarification=clarification,
                )
                raw_roles = await self._client.complete(
                    system,
                    user,
                    self._settings.llm_orchestrator_temperature,
                    model=active_model,
                )
                roles = parse_roles(raw_roles, expected_count=desired_count)
                await self._store.set_roles(run_id, roles)

            current_stage = RunStage.INDEPENDENT_ANALYSIS
            await self._store.start_stage(run_id, current_stage)
            await self._run_experts(run_id, record.decision, roles, active_model)

            if record.debate:
                current_stage = RunStage.DEBATE
                await self._store.start_stage(run_id, current_stage)
                await self._run_debate(run_id, record.decision, roles, active_model)

            snapshot = await self._store.get_record(run_id)
            active_opinions = [
                (
                    opinion.role,
                    opinion.rebuttal if record.debate else opinion.initial_analysis,
                )
                for opinion in snapshot.expert_opinions
            ]
            if any(analysis is None for _, analysis in active_opinions):
                raise ProviderProtocolError("an active expert opinion is missing")
            complete_active = [(role, analysis) for role, analysis in active_opinions if analysis]
            round_name = "rebuttal" if record.debate else "initial"

            current_stage = RunStage.DEVILS_ADVOCATE
            await self._store.start_stage(run_id, current_stage)
            system, user = advocate_prompt(
                record.decision,
                round_name=round_name,
                active_opinions=complete_active,
            )
            advocate = await self._client.complete(
                system,
                user,
                self._settings.llm_advocate_temperature,
                model=active_model,
            )
            await self._store.set_advocate(run_id, advocate)

            current_stage = RunStage.SYNTHESIS
            await self._store.start_stage(run_id, current_stage)
            system, user = synthesis_prompt(
                record.decision,
                round_name=round_name,
                active_opinions=complete_active,
                devils_advocate=advocate,
            )
            synthesis = await self._client.complete(
                system,
                user,
                self._settings.llm_merge_temperature,
                model=active_model,
            )
            await self._store.set_synthesis(run_id, synthesis)
            await self._store.complete_run(run_id)
        except asyncio.CancelledError:
            raise
        except MalformedRoles:
            await self._store.fail_run(
                run_id,
                RunError(
                    stage=current_stage,
                    code="malformed_roles",
                    message=(
                        "Role planning returned an invalid role set. Start a new run or use a "
                        "model that follows JSON output instructions."
                    ),
                    retryable=False,
                ),
            )
        except ProviderError as exc:
            await self._store.fail_run(run_id, self._provider_error(current_stage, exc))
        except Exception:
            logger.exception(
                "Unexpected run failure",
                extra={"run_id": str(run_id), "stage": current_stage.value},
            )
            await self._store.fail_run(
                run_id,
                RunError(
                    stage=current_stage,
                    code="internal_error",
                    message="The run stopped because of an internal error.",
                    retryable=False,
                ),
            )
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

    async def _capture(self, index: int, awaitable: Awaitable[str]) -> CallResult:
        try:
            return CallResult(index=index, output=await awaitable)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return CallResult(index=index, error=exc)

    async def _run_experts(
        self, run_id: UUID, decision: str, roles: list[RoleSpec], active_model: str
    ) -> None:
        tasks = []
        for index, role in enumerate(roles):
            system, user = expert_prompt(decision, role)
            tasks.append(
                asyncio.create_task(
                    self._capture(
                        index,
                        self._client.complete(
                            system,
                            user,
                            self._settings.llm_expert_temperature,
                            model=active_model,
                        ),
                    )
                )
            )

        errors: list[tuple[int, Exception]] = []
        for completed in asyncio.as_completed(tasks):
            result = await completed
            if result.error is not None:
                errors.append((result.index, result.error))
            elif result.output is not None:
                await self._store.set_expert_opinion(run_id, roles[result.index], result.output)
        if errors:
            raise sorted(errors, key=lambda item: item[0])[0][1]

    async def _run_debate(
        self, run_id: UUID, decision: str, roles: list[RoleSpec], active_model: str
    ) -> None:
        snapshot = await self._store.get_record(run_id)
        initial_by_name = {
            opinion.role.name: opinion.initial_analysis for opinion in snapshot.expert_opinions
        }
        tasks = []
        for index, role in enumerate(roles):
            opposing = [
                (other, initial_by_name[other.name]) for other in roles if other.name != role.name
            ]
            system, user = debate_prompt(
                decision,
                role,
                initial_by_name[role.name],
                opposing,
            )
            tasks.append(
                asyncio.create_task(
                    self._capture(
                        index,
                        self._client.complete(
                            system,
                            user,
                            self._settings.llm_debate_temperature,
                            model=active_model,
                        ),
                    )
                )
            )

        errors: list[tuple[int, Exception]] = []
        for completed in asyncio.as_completed(tasks):
            result = await completed
            if result.error is not None:
                errors.append((result.index, result.error))
            elif result.output is not None:
                await self._store.set_rebuttal(run_id, roles[result.index].name, result.output)
        if errors:
            raise sorted(errors, key=lambda item: item[0])[0][1]

    async def _heartbeat_loop(self, run_id: UUID) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            if not await self._store.append_heartbeat(run_id):
                return

    @staticmethod
    def _provider_error(stage: RunStage, error: ProviderError) -> RunError:
        stage_label = stage.value.replace("_", " ")
        if isinstance(error, ProviderTimeout):
            return RunError(
                stage=stage,
                code="provider_timeout",
                message=f"The model provider timed out during {stage_label}. Start a new run.",
                retryable=True,
            )
        if isinstance(error, ProviderHTTPError):
            return RunError(
                stage=stage,
                code="provider_http_error",
                message=f"The model provider failed during {stage_label}. Start a new run.",
                retryable=error.retryable,
            )
        return RunError(
            stage=stage,
            code="provider_protocol_error",
            message=f"The model provider returned an invalid response during {stage_label}.",
            retryable=False,
        )
