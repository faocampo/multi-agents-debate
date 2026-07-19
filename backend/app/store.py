from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .models import (
    ExpertOpinion,
    RoleSpec,
    RunError,
    RunEvent,
    RunEventType,
    RunRecord,
    RunStage,
    RunStatus,
    RunSummary,
    utc_now,
    validate_role_panel,
)


@dataclass(slots=True)
class StoredRun:
    record: RunRecord
    events: list[RunEvent]
    next_event_id: int
    condition: asyncio.Condition


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[UUID, StoredRun] = {}
        self._insertion_order: list[UUID] = []
        self._lock = asyncio.Lock()

    @staticmethod
    def _excerpt(decision: str) -> str:
        compact = " ".join(decision.split())
        return compact if len(compact) <= 160 else f"{compact[:160]}…"

    @classmethod
    def _summary(cls, record: RunRecord) -> RunSummary:
        return RunSummary(
            id=record.id,
            decision_excerpt=cls._excerpt(record.decision),
            debate=record.debate,
            status=record.status,
            stage=record.stage,
            role_count=len(record.roles),
            created_at=record.created_at,
            completed_at=record.completed_at,
        )

    @staticmethod
    def _is_terminal(record: RunRecord) -> bool:
        return record.status in {RunStatus.COMPLETED, RunStatus.FAILED}

    @staticmethod
    def _append_event(
        stored: StoredRun,
        event_type: RunEventType,
        data: dict[str, Any],
        *,
        timestamp: datetime | None = None,
    ) -> RunEvent:
        event = RunEvent(
            id=stored.next_event_id,
            run_id=stored.record.id,
            type=event_type,
            timestamp=timestamp or utc_now(),
            data=data,
        )
        stored.events.append(event)
        stored.next_event_id += 1
        stored.condition.notify_all()
        return event

    async def _stored(self, run_id: UUID) -> StoredRun:
        async with self._lock:
            stored = self._runs.get(run_id)
        if stored is None:
            raise KeyError(run_id)
        return stored

    async def create_run(
        self, decision: str, debate: bool, roles: list[RoleSpec] | None = None
    ) -> RunSummary:
        now = utc_now()
        validated_roles = validate_role_panel(roles) if roles else []
        record = RunRecord(
            id=uuid4(),
            decision=decision,
            debate=debate,
            status=RunStatus.QUEUED,
            stage=RunStage.QUEUED,
            created_at=now,
            roles=copy.deepcopy(validated_roles),
        )
        condition = asyncio.Condition(self._lock)
        stored = StoredRun(record=record, events=[], next_event_id=1, condition=condition)
        async with condition:
            self._runs[record.id] = stored
            self._insertion_order.append(record.id)
            summary = self._summary(record)
            self._append_event(
                stored,
                RunEventType.RUN_CREATED,
                {"summary": summary.model_dump(mode="json")},
                timestamp=now,
            )
        return copy.deepcopy(summary)

    async def get_record(self, run_id: UUID) -> RunRecord:
        stored = await self._stored(run_id)
        async with stored.condition:
            return copy.deepcopy(stored.record)

    async def list_summaries(self, limit: int) -> list[RunSummary]:
        async with self._lock:
            selected = reversed(self._insertion_order[-limit:])
            summaries = [self._summary(self._runs[run_id].record) for run_id in selected]
        return copy.deepcopy(summaries)

    async def start_stage(self, run_id: UUID, stage: RunStage) -> None:
        stored = await self._stored(run_id)
        async with stored.condition:
            if self._is_terminal(stored.record):
                return
            now = utc_now()
            stored.record.status = RunStatus.RUNNING
            stored.record.stage = stage
            if stored.record.started_at is None:
                stored.record.started_at = now
            self._append_event(
                stored,
                RunEventType.STAGE_STARTED,
                {"stage": stage.value},
                timestamp=now,
            )

    async def set_roles(self, run_id: UUID, roles: list[RoleSpec]) -> None:
        validated_roles = validate_role_panel(roles)
        stored = await self._stored(run_id)
        async with stored.condition:
            stored.record.roles = copy.deepcopy(validated_roles)
            self._append_event(
                stored,
                RunEventType.ROLES_PLANNED,
                {"roles": [role.model_dump(mode="json") for role in roles]},
            )

    async def set_expert_opinion(
        self, run_id: UUID, role: RoleSpec, analysis: str
    ) -> ExpertOpinion:
        stored = await self._stored(run_id)
        async with stored.condition:
            now = utc_now()
            opinion = ExpertOpinion(
                role=role,
                initial_analysis=analysis,
                initial_completed_at=now,
            )
            by_name = {item.role.name: item for item in stored.record.expert_opinions}
            by_name[role.name] = opinion
            stored.record.expert_opinions = [
                by_name[item.name] for item in stored.record.roles if item.name in by_name
            ]
            self._append_event(
                stored,
                RunEventType.EXPERT_COMPLETED,
                {"opinion": opinion.model_dump(mode="json")},
                timestamp=now,
            )
            return copy.deepcopy(opinion)

    async def set_rebuttal(self, run_id: UUID, role_name: str, rebuttal: str) -> None:
        stored = await self._stored(run_id)
        async with stored.condition:
            now = utc_now()
            for index, opinion in enumerate(stored.record.expert_opinions):
                if opinion.role.name == role_name:
                    stored.record.expert_opinions[index] = opinion.model_copy(
                        update={"rebuttal": rebuttal.strip(), "rebuttal_completed_at": now}
                    )
                    break
            else:
                raise KeyError(role_name)
            self._append_event(
                stored,
                RunEventType.DEBATE_COMPLETED,
                {
                    "role_name": role_name,
                    "rebuttal": rebuttal.strip(),
                    "completed_at": now.isoformat().replace("+00:00", "Z"),
                },
                timestamp=now,
            )

    async def set_advocate(self, run_id: UUID, analysis: str) -> None:
        stored = await self._stored(run_id)
        async with stored.condition:
            stored.record.advocate_analysis = analysis.strip()
            self._append_event(
                stored,
                RunEventType.ADVOCATE_COMPLETED,
                {"analysis": analysis.strip()},
            )

    async def set_synthesis(self, run_id: UUID, synthesis: str) -> None:
        stored = await self._stored(run_id)
        async with stored.condition:
            stored.record.synthesis = synthesis.strip()
            self._append_event(
                stored,
                RunEventType.SYNTHESIS_COMPLETED,
                {"synthesis": synthesis.strip()},
            )

    async def complete_run(self, run_id: UUID) -> None:
        stored = await self._stored(run_id)
        async with stored.condition:
            if self._is_terminal(stored.record):
                return
            now = utc_now()
            stored.record.status = RunStatus.COMPLETED
            stored.record.stage = RunStage.COMPLETED
            stored.record.completed_at = now
            self._append_event(
                stored,
                RunEventType.RUN_COMPLETED,
                {"summary": self._summary(stored.record).model_dump(mode="json")},
                timestamp=now,
            )

    async def fail_run(self, run_id: UUID, error: RunError) -> None:
        stored = await self._stored(run_id)
        async with stored.condition:
            if self._is_terminal(stored.record):
                return
            now = utc_now()
            stored.record.status = RunStatus.FAILED
            stored.record.stage = RunStage.FAILED
            stored.record.completed_at = now
            stored.record.error = error
            self._append_event(
                stored,
                RunEventType.RUN_FAILED,
                {
                    "error": error.model_dump(mode="json"),
                    "summary": self._summary(stored.record).model_dump(mode="json"),
                },
                timestamp=now,
            )

    async def append_heartbeat(self, run_id: UUID) -> bool:
        stored = await self._stored(run_id)
        async with stored.condition:
            if self._is_terminal(stored.record):
                return False
            self._append_event(
                stored,
                RunEventType.HEARTBEAT,
                {"status": stored.record.status.value, "stage": stored.record.stage.value},
            )
            return True

    async def latest_event_id(self, run_id: UUID) -> int:
        stored = await self._stored(run_id)
        async with stored.condition:
            return stored.next_event_id - 1

    async def wait_for_events(self, run_id: UUID, after_id: int) -> tuple[list[RunEvent], bool]:
        stored = await self._stored(run_id)
        async with stored.condition:
            while True:
                events = [event for event in stored.events if event.id > after_id]
                terminal = self._is_terminal(stored.record)
                if events or terminal:
                    return copy.deepcopy(events), terminal
                await stored.condition.wait()
