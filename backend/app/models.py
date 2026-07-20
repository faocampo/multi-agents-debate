from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


StrictText80 = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, min_length=1, max_length=80)
]
StrictText300 = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, min_length=1, max_length=300)
]
StrictText500 = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, min_length=1, max_length=500)
]
StrictText2000 = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, min_length=1, max_length=2000)
]
ClarificationQuestion = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, min_length=1, max_length=500)
]
DecisionText = Annotated[
    str, StringConstraints(strip_whitespace=True, strict=True, min_length=1, max_length=20_000)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RoleSource(StrEnum):
    PLANNED = "planned"
    LIBRARY = "library"


class RunStage(StrEnum):
    QUEUED = "queued"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    PLANNING_ROLES = "planning_roles"
    INDEPENDENT_ANALYSIS = "independent_analysis"
    DEBATE = "debate"
    DEVILS_ADVOCATE = "devils_advocate"
    SYNTHESIS = "synthesis"
    COMPLETED = "completed"
    FAILED = "failed"


class RunEventType(StrEnum):
    RUN_CREATED = "run.created"
    STAGE_STARTED = "stage.started"
    CLARIFICATION_REQUESTED = "clarification.requested"
    CLARIFICATION_ANSWERED = "clarification.answered"
    ROLES_PLANNED = "roles.planned"
    EXPERT_COMPLETED = "expert.completed"
    DEBATE_COMPLETED = "debate.completed"
    ADVOCATE_COMPLETED = "advocate.completed"
    SYNTHESIS_COMPLETED = "synthesis.completed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    HEARTBEAT = "heartbeat"


class RoleSpec(StrictModel):
    name: StrictText80
    focus: StrictText500
    bias: StrictText300
    prompt: StrictText2000 | None = None


def validate_role_panel(roles: list[RoleSpec]) -> list[RoleSpec]:
    if not 3 <= len(roles) <= 5:
        raise ValueError("role panel must contain three to five roles")
    normalized_names = {" ".join(role.name.split()).casefold() for role in roles}
    if len(normalized_names) != len(roles):
        raise ValueError("role names must be unique")
    return roles


class ExpertOpinion(StrictModel):
    role: RoleSpec
    initial_analysis: str
    initial_completed_at: datetime
    rebuttal: str | None = None
    rebuttal_completed_at: datetime | None = None

    @field_validator("initial_analysis", "rebuttal")
    @classmethod
    def validate_model_output(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("model output must not be empty")
        return normalized


class RunError(StrictModel):
    stage: RunStage
    code: str
    message: str
    retryable: bool

    @field_validator("stage")
    @classmethod
    def validate_failure_stage(cls, value: RunStage) -> RunStage:
        if value in {RunStage.QUEUED, RunStage.COMPLETED, RunStage.FAILED}:
            raise ValueError("error stage must be a model-backed stage")
        return value


class RunSummary(StrictModel):
    id: UUID
    decision_excerpt: str
    debate: bool
    status: RunStatus
    stage: RunStage
    role_count: int = Field(ge=0, le=5)
    created_at: datetime
    completed_at: datetime | None = None


class RunRecord(StrictModel):
    id: UUID
    decision: DecisionText
    debate: bool
    clarify: bool = False
    status: RunStatus
    stage: RunStage
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    clarifying_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=5)
    clarifying_answers: list[StrictText2000] | None = None
    clarification_skipped: bool = False
    roles: list[RoleSpec] = Field(default_factory=list, max_length=5)
    expert_opinions: list[ExpertOpinion] = Field(default_factory=list, max_length=5)
    advocate_analysis: str | None = None
    synthesis: str | None = None
    error: RunError | None = None


class RunEvent(StrictModel):
    id: int = Field(ge=1)
    run_id: UUID
    type: RunEventType
    timestamp: datetime
    data: dict[str, Any]


class CreateRunRequest(StrictModel):
    decision: DecisionText
    debate: bool = True
    clarify: bool = False
    role_source: RoleSource = RoleSource.PLANNED


class SubmitClarificationRequest(StrictModel):
    skipped: bool = False
    answers: list[StrictText2000] = Field(default_factory=list, max_length=5)


# --- Role library (Settings) -------------------------------------------------


class RoleDefinition(StrictModel):
    """A user-defined role persisted in the role library.

    The ``prompt`` field is an optional free-form expert instruction. It is
    forwarded to the expert model as part of the untrusted role mandate (never
    as a system prompt) so user-supplied text cannot override trusted system
    instructions.
    """

    id: UUID
    name: StrictText80
    focus: StrictText500
    bias: StrictText300
    prompt: StrictText2000 | None = None


class CreateRoleRequest(StrictModel):
    name: StrictText80
    focus: StrictText500
    bias: StrictText300
    prompt: StrictText2000 | None = None


class RoleLibrarySettings(StrictModel):
    default_role_count: int = Field(default=3, ge=3, le=5)
    llm_model: str | None = None
    roles: list[RoleDefinition] = Field(default_factory=list, max_length=100)

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LLMModelInfo(StrictModel):
    """Public model metadata returned by the provider list endpoint."""

    id: str
    name: str
    description: str | None = None


class UpdateRoleLibrarySettingsRequest(StrictModel):
    default_role_count: int | None = Field(default=None, ge=3, le=5)
    llm_model: str | None = None

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("llm_model must not be empty")
        return normalized
