from __future__ import annotations

import asyncio
import copy
import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from .models import (
    CreateRoleRequest,
    RoleDefinition,
    RoleLibrarySettings,
    RoleSpec,
    UpdateRoleLibrarySettingsRequest,
    validate_role_panel,
)

logger = logging.getLogger(__name__)
MAX_ROLE_LIBRARY_SIZE = 100


class RoleNotFound(KeyError):
    def __init__(self, role_id: UUID) -> None:
        super().__init__(role_id)
        self.role_id = role_id


class DuplicateRoleName(ValueError):
    pass


class RoleLibraryFull(ValueError):
    pass


class InsufficientLibraryRoles(ValueError):
    def __init__(self, required: int, available: int) -> None:
        super().__init__(required, available)
        self.required = required
        self.available = available


class RolePersistenceError(RuntimeError):
    pass


class RoleLibraryStore:
    """JSON-file-backed library of user-defined agent roles.

    The store keeps an in-memory copy synchronized with a JSON file on disk so
    settings survive backend restarts. All public methods are async and
    serialized through a lock; mutations flush to disk before returning.
    """

    def __init__(self, path: Path, default_llm_model: str | None = None) -> None:
        self._path = path
        self._default_llm_model = default_llm_model
        self._lock = asyncio.Lock()
        self._settings = RoleLibrarySettings()
        self._loaded = False

    async def _load(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            try:
                self._settings = await asyncio.to_thread(self._read_file)
            except (json.JSONDecodeError, ValidationError, ValueError):
                try:
                    await asyncio.to_thread(self._quarantine_invalid_file)
                except OSError as exc:
                    raise RolePersistenceError(
                        "Could not preserve the invalid role library."
                    ) from exc
                logger.warning("roles file at %s was invalid; starting empty", self._path)
                self._settings = RoleLibrarySettings()
            except OSError as exc:
                raise RolePersistenceError("Could not read the role library.") from exc
            self._loaded = True

    def _read_file(self) -> RoleLibrarySettings:
        if not self._path.exists():
            return RoleLibrarySettings()
        with self._path.open(encoding="utf-8") as handle:
            data: Any = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("role library must be a JSON object")
        return RoleLibrarySettings.model_validate(data)

    def _quarantine_invalid_file(self) -> None:
        if not self._path.exists():
            return
        backup = self._path.with_name(f"{self._path.name}.invalid")
        suffix = 1
        while backup.exists():
            backup = self._path.with_name(f"{self._path.name}.invalid.{suffix}")
            suffix += 1
        self._path.replace(backup)

    def _write_file(self, settings: RoleLibrarySettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = settings.model_dump(mode="json")
        temporary = self._path.with_suffix(f"{self._path.suffix}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            temporary.replace(self._path)
        finally:
            temporary.unlink(missing_ok=True)

    async def _persist(self, candidate: RoleLibrarySettings) -> None:
        try:
            await asyncio.to_thread(self._write_file, candidate)
        except OSError as exc:
            raise RolePersistenceError("Could not save the role library.") from exc

    @staticmethod
    def _names(roles: list[RoleDefinition]) -> set[str]:
        return {" ".join(role.name.split()).casefold() for role in roles}

    def _effective_settings(self) -> RoleLibrarySettings:
        settings = copy.deepcopy(self._settings)
        if not settings.llm_model and self._default_llm_model:
            settings.llm_model = self._default_llm_model
        return settings

    async def get_settings(self) -> RoleLibrarySettings:
        await self._load()
        async with self._lock:
            return self._effective_settings()

    async def update_settings(
        self, payload: UpdateRoleLibrarySettingsRequest
    ) -> RoleLibrarySettings:
        await self._load()
        async with self._lock:
            updates: dict[str, Any] = {}
            if payload.default_role_count is not None:
                updates["default_role_count"] = payload.default_role_count
            if payload.llm_model is not None:
                updates["llm_model"] = payload.llm_model
            candidate = self._settings.model_copy(update=updates, deep=True)
            await self._persist(candidate)
            self._settings = candidate
            return self._effective_settings()

    async def list_roles(self) -> list[RoleDefinition]:
        await self._load()
        async with self._lock:
            return copy.deepcopy(self._settings.roles)

    async def create_role(self, payload: CreateRoleRequest) -> RoleDefinition:
        await self._load()
        async with self._lock:
            if len(self._settings.roles) >= MAX_ROLE_LIBRARY_SIZE:
                raise RoleLibraryFull
            new_name = " ".join(payload.name.split()).casefold()
            if new_name in self._names(self._settings.roles):
                raise DuplicateRoleName(payload.name)
            role = RoleDefinition(id=uuid4(), **payload.model_dump())
            candidate = self._settings.model_copy(update={"roles": [*self._settings.roles, role]})
            await self._persist(candidate)
            self._settings = candidate
            return copy.deepcopy(role)

    async def replace_role(self, role_id: UUID, payload: CreateRoleRequest) -> RoleDefinition:
        await self._load()
        async with self._lock:
            index = self._index_of(role_id)
            new_name = " ".join(payload.name.split()).casefold()
            for offset, existing in enumerate(self._settings.roles):
                if offset != index and " ".join(existing.name.split()).casefold() == new_name:
                    raise DuplicateRoleName(payload.name)
            role = RoleDefinition(id=role_id, **payload.model_dump())
            roles = [*self._settings.roles]
            roles[index] = role
            candidate = self._settings.model_copy(update={"roles": roles})
            await self._persist(candidate)
            self._settings = candidate
            return copy.deepcopy(role)

    async def delete_role(self, role_id: UUID) -> None:
        await self._load()
        async with self._lock:
            index = self._index_of(role_id)
            roles = [*self._settings.roles]
            roles.pop(index)
            candidate = self._settings.model_copy(update={"roles": roles})
            await self._persist(candidate)
            self._settings = candidate

    def _index_of(self, role_id: UUID) -> int:
        for index, role in enumerate(self._settings.roles):
            if role.id == role_id:
                return index
        raise RoleNotFound(role_id)

    async def select_default_specs(self) -> list[RoleSpec]:
        await self._load()
        async with self._lock:
            required = self._settings.default_role_count
            if len(self._settings.roles) < required:
                raise InsufficientLibraryRoles(required, len(self._settings.roles))
            selected = self._settings.roles[:required]
            return validate_role_panel(
                [
                    RoleSpec(
                        name=role.name,
                        focus=role.focus,
                        bias=role.bias,
                        prompt=role.prompt,
                    )
                    for role in selected
                ]
            )
