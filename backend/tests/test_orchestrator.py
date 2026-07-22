from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

import pytest

from app.config import Settings
from app.models import RunEventType, RunStage, RunStatus, UpdateRoleLibrarySettingsRequest
from app.orchestrator import RunExecutor
from app.prompts import (
    ADVOCATE_SYSTEM,
    CHALLENGE_ADVOCATE_RESPONSE_SYSTEM,
    CHALLENGE_ADVOCATE_SYSTEM,
    CHALLENGE_PEER_DEBATE_SYSTEM,
    CHALLENGE_RECONSIDERATION_SYSTEM,
    CHALLENGE_SYNTHESIS_SYSTEM,
    EXPERT_SYSTEM,
    ROLE_PLANNER_SYSTEM,
)
from app.role_store import RoleLibraryStore
from app.store import RunStore
from tests.fakes import ROLES, ScriptedClient


def settings() -> Settings:
    return Settings(_env_file=None)


async def execute(
    debate: bool, client: ScriptedClient | None = None
) -> tuple[RunStore, UUID, ScriptedClient]:
    store = RunStore()
    summary = await store.create_run("Make a consequential decision", debate)
    fake = client or ScriptedClient()
    await RunExecutor(store, fake, settings(), heartbeat_interval=3600).run(summary.id)
    return store, summary.id, fake


@pytest.mark.asyncio
@pytest.mark.parametrize(("debate", "expected_calls"), [(False, 6), (True, 9)])
async def test_call_counts_and_terminal_state(debate: bool, expected_calls: int) -> None:
    store, run_id, client = await execute(debate)

    record = await store.get_record(run_id)
    events, terminal = await store.wait_for_events(run_id, 0)
    assert record.status is RunStatus.COMPLETED
    assert record.synthesis == "## Verdict\n\nRun a reversible pilot."
    assert len(client.calls) == expected_calls
    assert terminal is True
    assert events[0].type is RunEventType.RUN_CREATED
    assert events[-1].type is RunEventType.RUN_COMPLETED


@pytest.mark.asyncio
async def test_clarification_pauses_before_role_planning_and_resumes_with_answers() -> None:
    store = RunStore()
    summary = await store.create_run("Decide with context", False, clarify=True)
    client = ScriptedClient()
    task = asyncio.create_task(
        RunExecutor(store, client, settings(), heartbeat_interval=3600).run(summary.id)
    )

    for _ in range(100):
        record = await store.get_record(summary.id)
        if record.stage is RunStage.AWAITING_CLARIFICATION:
            break
        await asyncio.sleep(0.001)
    else:
        raise AssertionError("run did not request clarification")

    assert len([call for call in client.calls if call.system.startswith(ROLE_PLANNER_SYSTEM)]) == 0
    await store.submit_clarification(
        summary.id,
        answers=["A safe pilot", "Customers and operators"],
        skipped=False,
    )
    await task

    record = await store.get_record(summary.id)
    assert record.status is RunStatus.COMPLETED
    assert record.clarifying_answers == ["A safe pilot", "Customers and operators"]
    assert len([call for call in client.calls if call.system.startswith(ROLE_PLANNER_SYSTEM)]) == 1
    planner_payload = json.loads(
        next(call.user for call in client.calls if call.system.startswith(ROLE_PLANNER_SYSTEM))
    )
    assert planner_payload["clarification"][0]["answer"] == "A safe pilot"


@pytest.mark.asyncio
async def test_first_round_is_independent_and_merge_uses_rebuttals() -> None:
    _, _, client = await execute(True)

    expert_calls = [call for call in client.calls if call.system == EXPERT_SYSTEM]
    assert len(expert_calls) == len(ROLES)
    for call in expert_calls:
        assert set(json.loads(call.user)) == {"decision", "role"}

    advocate_call = next(call for call in client.calls if call.system == ADVOCATE_SYSTEM)
    advocate_payload = json.loads(advocate_call.user)
    assert advocate_payload["round"] == "rebuttal"
    assert all(
        item["analysis"].startswith("## Revised recommendation")
        for item in advocate_payload["active_opinions"]
    )


@pytest.mark.asyncio
async def test_challenge_reuses_roles_and_runs_full_challenge_pipeline() -> None:
    store, parent_id, parent_client = await execute(True)
    child_summary = await store.create_challenge_run(
        parent_id,
        kind="challenge",
        challenge_input="What if the implementation risk is higher?",
    )
    child_client = ScriptedClient()

    await RunExecutor(store, child_client, settings(), heartbeat_interval=3600).run(child_summary.id)

    child = await store.get_record(child_summary.id)
    assert child.status is RunStatus.COMPLETED
    assert [role.name for role in child.roles] == [role["name"] for role in ROLES]
    assert len(child_client.calls) == 11
    assert not any(call.system.startswith(ROLE_PLANNER_SYSTEM) for call in child_client.calls)
    assert len([call for call in child_client.calls if call.system == CHALLENGE_RECONSIDERATION_SYSTEM]) == 3
    assert len([call for call in child_client.calls if call.system == CHALLENGE_PEER_DEBATE_SYSTEM]) == 3
    assert len([call for call in child_client.calls if call.system == CHALLENGE_ADVOCATE_SYSTEM]) == 1
    assert len([call for call in child_client.calls if call.system == CHALLENGE_ADVOCATE_RESPONSE_SYSTEM]) == 3
    assert len([call for call in child_client.calls if call.system == CHALLENGE_SYNTHESIS_SYSTEM]) == 1
    assert all(opinion.advocate_response for opinion in child.expert_opinions)
    assert child.challenge is not None
    assert child.challenge.parent_conclusion == (await store.get_record(parent_id)).synthesis
    assert len(parent_client.calls) == 9


@pytest.mark.asyncio
async def test_challenge_failure_reports_active_challenge_stage() -> None:
    store, parent_id, _ = await execute(True)
    child_summary = await store.create_challenge_run(
        parent_id,
        kind="challenge",
        challenge_input="What if the implementation risk is higher?",
    )
    client = ScriptedClient(fail_system=CHALLENGE_ADVOCATE_RESPONSE_SYSTEM)

    await RunExecutor(store, client, settings(), heartbeat_interval=3600).run(child_summary.id)

    child = await store.get_record(child_summary.id)
    assert child.status is RunStatus.FAILED
    assert child.error is not None
    assert child.error.stage is RunStage.CHALLENGE_ADVOCATE_RESPONSE
    assert all(opinion.rebuttal for opinion in child.expert_opinions)
    assert child.synthesis is None


@pytest.mark.asyncio
async def test_timeout_preserves_completed_outputs_and_fails_stage() -> None:
    store, run_id, _ = await execute(False, ScriptedClient(fail_system=ADVOCATE_SYSTEM))

    record = await store.get_record(run_id)
    events, _ = await store.wait_for_events(run_id, 0)
    assert record.status is RunStatus.FAILED
    assert record.stage is RunStage.FAILED
    assert record.error is not None
    assert record.error.stage is RunStage.DEVILS_ADVOCATE
    assert record.error.code == "provider_timeout"
    assert len(record.expert_opinions) == len(ROLES)
    assert record.advocate_analysis is None
    assert events[-1].type is RunEventType.RUN_FAILED


class BarrierClient(ScriptedClient):
    def __init__(self) -> None:
        super().__init__()
        self.started = 0
        self.all_started = asyncio.Event()
        self.release = asyncio.Event()

    async def complete(
        self, system: str, user: str, temperature: float, model: str | None = None
    ) -> str:
        if system == EXPERT_SYSTEM:
            self.started += 1
            if self.started == len(ROLES):
                self.all_started.set()
            await self.release.wait()
        return await super().complete(system, user, temperature, model)


@pytest.mark.asyncio
async def test_experts_start_in_parallel() -> None:
    store = RunStore()
    summary = await store.create_run("Decide in parallel", False)
    client = BarrierClient()
    task = asyncio.create_task(
        RunExecutor(store, client, settings(), heartbeat_interval=3600).run(summary.id)
    )

    await asyncio.wait_for(client.all_started.wait(), timeout=1)
    assert client.started == len(ROLES)
    client.release.set()
    await task


@pytest.mark.asyncio
async def test_uses_library_selected_model(tmp_path: Path) -> None:
    library = RoleLibraryStore(tmp_path / "roles.json", default_llm_model="environment-model")
    await library.update_settings(UpdateRoleLibrarySettingsRequest(llm_model="selected-model"))

    store = RunStore()
    summary = await store.create_run("Make a consequential decision", False)
    client = ScriptedClient()
    await RunExecutor(
        store, client, Settings(_env_file=None), heartbeat_interval=3600, role_library=library
    ).run(summary.id)

    assert all(call.model == "selected-model" for call in client.calls)
