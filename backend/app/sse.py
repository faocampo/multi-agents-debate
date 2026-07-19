from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID

from .models import RunEvent
from .store import RunStore


def serialize_event(event: RunEvent) -> str:
    payload = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"id: {event.id}\nevent: {event.type.value}\ndata: {payload}\n\n"


async def event_stream(store: RunStore, run_id: UUID, cursor: int) -> AsyncIterator[str]:
    while True:
        events, terminal = await store.wait_for_events(run_id, cursor)
        for event in events:
            yield serialize_event(event)
            cursor = event.id
        if terminal:
            return
