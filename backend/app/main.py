from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .client import HttpxLLMClient, LLMClient, ProviderError
from .config import Settings
from .models import (
    CreateRoleRequest,
    CreateRunRequest,
    LLMModelInfo,
    RoleDefinition,
    RoleLibrarySettings,
    RoleSource,
    RunRecord,
    RunSummary,
    SubmitClarificationRequest,
    UpdateRoleLibrarySettingsRequest,
)
from .orchestrator import RunExecutor
from .role_store import (
    DuplicateRoleName,
    InsufficientLibraryRoles,
    RoleLibraryFull,
    RoleLibraryStore,
    RoleNotFound,
    RolePersistenceError,
)
from .sse import event_stream
from .store import RunStore, StageConflictError

logger = logging.getLogger(__name__)


def create_app(
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
    *,
    heartbeat_interval: float = 15,
    role_library: RoleLibraryStore | None = None,
) -> FastAPI:
    configured_settings = settings or Settings()
    store = RunStore()
    library = role_library or RoleLibraryStore(
        configured_settings.roles_file,
        default_llm_model=configured_settings.llm_model,
    )
    background_tasks: set[asyncio.Task[None]] = set()
    owned_client: HttpxLLMClient | None = None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        nonlocal owned_client
        await library.get_settings()  # eager-load the persisted library
        active_client = llm_client
        if active_client is None:
            owned_client = HttpxLLMClient(configured_settings)
            active_client = owned_client
        application.state.llm_client = active_client
        application.state.executor = RunExecutor(
            store,
            active_client,
            configured_settings,
            heartbeat_interval=heartbeat_interval,
            role_library=library,
        )
        yield
        for task in background_tasks:
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        if owned_client is not None:
            await owned_client.aclose()

    application = FastAPI(
        title="AI Swarm Analysis API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.store = store
    application.state.role_library = library
    application.state.background_tasks = background_tasks

    @application.exception_handler(RolePersistenceError)
    async def role_persistence_error(
        _request: Request, _error: RolePersistenceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "The role library is temporarily unavailable."},
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Content-Type", "Last-Event-ID"],
        expose_headers=["Location"],
    )

    @application.post(
        "/api/runs",
        response_model=RunSummary,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_run(payload: CreateRunRequest, response: Response) -> RunSummary:
        roles = None
        if payload.role_source is RoleSource.LIBRARY:
            try:
                roles = await library.select_default_specs()
            except InsufficientLibraryRoles as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"The role library needs at least {exc.required} roles; "
                        f"only {exc.available} are available."
                    ),
                ) from exc
        summary = await store.create_run(payload.decision, payload.debate, roles, payload.clarify)
        response.headers["Location"] = f"/api/runs/{summary.id}"
        executor: RunExecutor = application.state.executor
        task = asyncio.create_task(executor.run(summary.id))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return summary

    @application.get("/api/runs", response_model=list[RunSummary])
    async def list_runs(limit: int = Query(default=20, ge=1, le=100)) -> list[RunSummary]:
        return await store.list_summaries(limit)

    @application.get("/api/runs/{run_id}", response_model=RunRecord)
    async def get_run(run_id: UUID) -> RunRecord:
        try:
            return await store.get_record(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

    @application.post("/api/runs/{run_id}/clarification", status_code=status.HTTP_204_NO_CONTENT)
    async def submit_clarification(
        run_id: UUID, payload: SubmitClarificationRequest
    ) -> Response:
        try:
            await store.submit_clarification(
                run_id,
                answers=payload.answers,
                skipped=payload.skipped,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc
        except StageConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.get("/api/runs/{run_id}/events")
    async def stream_events(
        run_id: UUID,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        try:
            latest_id = await store.latest_event_id(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc

        try:
            cursor = 0 if last_event_id is None else int(last_event_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID") from exc
        if cursor < 0 or cursor > latest_id:
            raise HTTPException(status_code=400, detail="Invalid Last-Event-ID")

        return StreamingResponse(
            event_stream(store, run_id, cursor),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @application.get("/api/settings", response_model=RoleLibrarySettings)
    async def get_settings() -> RoleLibrarySettings:
        return await library.get_settings()

    @application.patch("/api/settings", response_model=RoleLibrarySettings)
    async def update_settings(
        payload: UpdateRoleLibrarySettingsRequest,
    ) -> RoleLibrarySettings:
        return await library.update_settings(payload)

    @application.get("/api/models", response_model=list[LLMModelInfo])
    async def list_models(zdr: bool = Query(default=False)) -> list[LLMModelInfo]:
        llm_client: LLMClient = application.state.llm_client
        try:
            return await llm_client.list_models(zdr=zdr)
        except ProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not fetch models from provider",
            ) from exc

    @application.get("/api/settings/roles", response_model=list[RoleDefinition])
    async def list_roles() -> list[RoleDefinition]:
        return await library.list_roles()

    @application.post(
        "/api/settings/roles",
        response_model=RoleDefinition,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_role(payload: CreateRoleRequest, response: Response) -> RoleDefinition:
        try:
            role = await library.create_role(payload)
        except DuplicateRoleName as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A role with that name already exists.",
            ) from exc
        except RoleLibraryFull as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The role library can contain at most 100 roles.",
            ) from exc
        response.headers["Location"] = f"/api/settings/roles/{role.id}"
        return role

    @application.put("/api/settings/roles/{role_id}", response_model=RoleDefinition)
    async def replace_role(role_id: UUID, payload: CreateRoleRequest) -> RoleDefinition:
        try:
            return await library.replace_role(role_id, payload)
        except RoleNotFound as exc:
            raise HTTPException(status_code=404, detail="Role not found") from exc
        except DuplicateRoleName as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A role with that name already exists.",
            ) from exc

    @application.delete("/api/settings/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_role(role_id: UUID) -> Response:
        try:
            await library.delete_role(role_id)
        except RoleNotFound as exc:
            raise HTTPException(status_code=404, detail="Role not found") from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return application


app = create_app()
