from __future__ import annotations

import asyncio
import json
from uuid import UUID

import pytest

from app.config import Settings
from app.models import RunEventType, RunStage, RunStatus
from app.orchestrator import RunExecutor
from app.prompts import ADVOCATE_SYSTEM, EXPERT_SYSTEM
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

    async def complete(self, system: str, user: str, temperature: float) -> str:
        if system == EXPERT_SYSTEM:
            self.started += 1
            if self.started == len(ROLES):
                self.all_started.set()
            await self.release.wait()
        return await super().complete(system, user, temperature)


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
