from __future__ import annotations

import json

import pytest

from app.models import RoleSpec, RunError, RunEventType, RunStage
from app.sse import event_stream, serialize_event
from app.store import RunStore


@pytest.mark.asyncio
async def test_sse_replay_is_ordered_and_closes_after_terminal_event() -> None:
    store = RunStore()
    summary = await store.create_run("Replay a run", False)
    await store.start_stage(summary.id, RunStage.PLANNING_ROLES)
    await store.set_roles(
        summary.id,
        [
            RoleSpec(name="A", focus="A focus", bias="A bias"),
            RoleSpec(name="B", focus="B focus", bias="B bias"),
            RoleSpec(name="C", focus="C focus", bias="C bias"),
        ],
    )
    await store.fail_run(
        summary.id,
        RunError(
            stage=RunStage.PLANNING_ROLES,
            code="internal_error",
            message="Safe failure",
            retryable=False,
        ),
    )

    replay = [chunk async for chunk in event_stream(store, summary.id, 1)]
    assert [int(chunk.splitlines()[0].removeprefix("id: ")) for chunk in replay] == [2, 3, 4]
    assert "event: run.failed" in replay[-1]


@pytest.mark.asyncio
async def test_heartbeat_is_buffered_with_monotonic_id() -> None:
    store = RunStore()
    summary = await store.create_run("Heartbeat", False)
    await store.start_stage(summary.id, RunStage.PLANNING_ROLES)
    assert await store.append_heartbeat(summary.id) is True

    events, _ = await store.wait_for_events(summary.id, 0)
    assert [event.id for event in events] == [1, 2, 3]
    assert events[-1].type is RunEventType.HEARTBEAT
    wire = serialize_event(events[-1])
    assert wire.startswith("id: 3\nevent: heartbeat\ndata: ")
    assert wire.endswith("\n\n")
    payload = json.loads(wire.split("data: ", 1)[1])
    assert payload["id"] == 3
