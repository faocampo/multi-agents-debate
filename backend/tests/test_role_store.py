from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.config import Settings
from app.models import CreateRoleRequest, UpdateRoleLibrarySettingsRequest
from app.role_store import (
    DuplicateRoleName,
    InsufficientLibraryRoles,
    RoleLibraryFull,
    RoleLibraryStore,
    RoleNotFound,
    RolePersistenceError,
)


@pytest.mark.asyncio
async def test_default_settings_when_no_file(tmp_path: Path) -> None:
    store = RoleLibraryStore(tmp_path / "roles.json")
    settings = await store.get_settings()
    assert settings.default_role_count == 3
    assert settings.roles == []


@pytest.mark.asyncio
async def test_create_list_replace_delete_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "roles.json"
    store = RoleLibraryStore(path)

    created = await store.create_role(
        CreateRoleRequest(
            name="Customer Advocate",
            focus="Adoption and usability",
            bias="Prefer reversible choices",
            prompt="Challenge adoption assumptions.",
        )
    )
    assert created.id is not None
    assert created.prompt == "Challenge adoption assumptions."

    listed = await store.list_roles()
    assert [role.id for role in listed] == [created.id]

    replaced = await store.replace_role(
        created.id,
        CreateRoleRequest(
            name="Customer Advocate",
            focus="Adoption and usability",
            bias="Prefer reversible choices",
            prompt=None,
        ),
    )
    assert replaced.prompt is None
    assert replaced.id == created.id

    await store.delete_role(created.id)
    assert await store.list_roles() == []

    with pytest.raises(RoleNotFound):
        await store.replace_role(created.id, CreateRoleRequest(name="x", focus="y", bias="z"))


@pytest.mark.asyncio
async def test_duplicate_name_rejected(tmp_path: Path) -> None:
    store = RoleLibraryStore(tmp_path / "roles.json")
    await store.create_role(CreateRoleRequest(name="Engineer", focus="Delivery", bias="Ship"))
    with pytest.raises(DuplicateRoleName):
        await store.create_role(CreateRoleRequest(name="engineer", focus="x", bias="y"))


@pytest.mark.asyncio
async def test_update_settings_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "roles.json"
    store = RoleLibraryStore(path)
    updated = await store.update_settings(UpdateRoleLibrarySettingsRequest(default_role_count=5))
    assert updated.default_role_count == 5

    reopened = RoleLibraryStore(path)
    settings = await reopened.get_settings()
    assert settings.default_role_count == 5


@pytest.mark.asyncio
async def test_select_default_specs_requires_configured_count(tmp_path: Path) -> None:
    store = RoleLibraryStore(tmp_path / "roles.json")
    await store.create_role(CreateRoleRequest(name="A", focus="a-focus", bias="a-bias", prompt="p"))
    await store.create_role(CreateRoleRequest(name="B", focus="b-focus", bias="b-bias"))

    with pytest.raises(InsufficientLibraryRoles):
        await store.select_default_specs()

    await store.create_role(CreateRoleRequest(name="C", focus="c-focus", bias="c-bias"))
    specs = await store.select_default_specs()
    assert [spec.name for spec in specs] == ["A", "B", "C"]
    assert specs[0].prompt == "p"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["{not valid json", '{"default_role_count": 2, "roles": []}'])
async def test_invalid_file_is_preserved_and_starts_empty(tmp_path: Path, content: str) -> None:
    path = tmp_path / "roles.json"
    path.write_text(content, encoding="utf-8")
    store = RoleLibraryStore(path)

    settings = await store.get_settings()

    assert settings.roles == []
    assert settings.default_role_count == 3
    exists, backups = await asyncio.to_thread(
        lambda: (path.exists(), list(tmp_path.glob("roles.json.invalid*")))
    )
    assert not exists
    assert len(backups) == 1
    assert await asyncio.to_thread(backups[0].read_text, encoding="utf-8") == content


@pytest.mark.asyncio
async def test_failed_persistence_does_not_mutate_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RoleLibraryStore(tmp_path / "roles.json")
    await store.get_settings()

    def fail_write(*_: object) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(store, "_write_file", fail_write)
    with pytest.raises(RolePersistenceError):
        await store.create_role(CreateRoleRequest(name="A", focus="focus", bias="bias"))
    assert (await store.get_settings()).roles == []


@pytest.mark.asyncio
async def test_library_size_is_bounded(tmp_path: Path) -> None:
    store = RoleLibraryStore(tmp_path / "roles.json")
    for index in range(100):
        await store.create_role(CreateRoleRequest(name=f"Role {index}", focus="focus", bias="bias"))

    with pytest.raises(RoleLibraryFull):
        await store.create_role(CreateRoleRequest(name="Overflow", focus="focus", bias="bias"))


@pytest.mark.asyncio
async def test_llm_model_default_is_effective_but_not_persisted(tmp_path: Path) -> None:
    default_model = Settings(_env_file=None).llm_model
    store = RoleLibraryStore(tmp_path / "roles.json", default_llm_model=default_model)
    settings = await store.get_settings()
    assert settings.llm_model == default_model

    # The file should not acquire the default value just from reading it.
    reopened_default = RoleLibraryStore(tmp_path / "roles.json")
    assert (await reopened_default.get_settings()).llm_model is None

    await store.update_settings(UpdateRoleLibrarySettingsRequest(llm_model="selected-model"))
    assert (await store.get_settings()).llm_model == "selected-model"

    reopened = RoleLibraryStore(tmp_path / "roles.json")
    assert (await reopened.get_settings()).llm_model == "selected-model"
