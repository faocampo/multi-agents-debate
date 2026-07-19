from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.role_store import RoleLibraryStore
from tests.fakes import ScriptedClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def api_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(_env_file=None)
    library = RoleLibraryStore(tmp_path / "roles.json", default_llm_model=settings.llm_model)
    application = create_app(ScriptedClient(), settings, role_library=library)
    async with application.router.lifespan_context(application):
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def wait_for_terminal(client: httpx.AsyncClient, run_id: str) -> dict[str, object]:
    for _ in range(100):
        response = await client.get(f"/api/runs/{run_id}")
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        await asyncio.sleep(0.01)
    raise AssertionError("run did not reach a terminal state")


@pytest.mark.asyncio
async def test_create_list_snapshot_and_completed_replay(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/api/runs", json={"decision": "  Decide well  "})

    assert response.status_code == 202
    summary = response.json()
    assert summary["status"] == "queued"
    assert summary["debate"] is True
    assert response.headers["Location"] == f"/api/runs/{summary['id']}"

    record = await wait_for_terminal(api_client, summary["id"])
    assert record["decision"] == "Decide well"
    assert record["status"] == "completed"
    assert len(record["roles"]) == 3  # type: ignore[arg-type]

    history = (await api_client.get("/api/runs?limit=20")).json()
    assert history[0]["id"] == summary["id"]

    stream = await api_client.get(f"/api/runs/{summary['id']}/events")
    assert stream.status_code == 200
    assert "event: run.created" in stream.text
    assert "event: run.completed" in stream.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"decision": ""},
        {"decision": "   "},
        {"decision": "x" * 20_001},
        {"decision": 123},
        {"decision": "valid", "extra": True},
    ],
)
async def test_create_validation(api_client: httpx.AsyncClient, payload: dict[str, object]) -> None:
    response = await api_client.post("/api/runs", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_run_and_invalid_event_cursor(api_client: httpx.AsyncClient) -> None:
    missing = await api_client.get("/api/runs/2d8f795e-0aa0-4e3c-a4b9-4079d99df365")
    assert missing.status_code == 404

    created = await api_client.post("/api/runs", json={"decision": "Cursor test", "debate": False})
    run_id = created.json()["id"]
    invalid = await api_client.get(
        f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "999999"}
    )
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_list_limit_validation(api_client: httpx.AsyncClient) -> None:
    assert (await api_client.get("/api/runs?limit=0")).status_code == 422
    assert (await api_client.get("/api/runs?limit=101")).status_code == 422


@pytest.mark.asyncio
async def test_settings_crud_round_trip(api_client: httpx.AsyncClient) -> None:
    initial = (await api_client.get("/api/settings")).json()
    assert initial["default_role_count"] == 3
    assert initial["llm_model"] == Settings(_env_file=None).llm_model
    assert initial["roles"] == []

    updated = (await api_client.patch("/api/settings", json={"default_role_count": 4})).json()
    assert updated["default_role_count"] == 4

    created = await api_client.post(
        "/api/settings/roles",
        json={
            "name": "Engineer",
            "focus": "Delivery risk",
            "bias": "Prefer reversible systems",
            "prompt": "Stress-test delivery timelines.",
        },
    )
    assert created.status_code == 201
    role = created.json()
    assert role["prompt"] == "Stress-test delivery timelines."
    assert created.headers["Location"] == f"/api/settings/roles/{role['id']}"

    listed = (await api_client.get("/api/settings/roles")).json()
    assert [r["id"] for r in listed] == [role["id"]]

    replaced = await api_client.put(
        f"/api/settings/roles/{role['id']}",
        json={"name": "Engineer", "focus": "Delivery risk", "bias": "Ship fast", "prompt": None},
    )
    assert replaced.json()["bias"] == "Ship fast"
    assert replaced.json()["prompt"] is None

    deleted = await api_client.delete(f"/api/settings/roles/{role['id']}")
    assert deleted.status_code == 204
    assert (await api_client.get("/api/settings/roles")).json() == []


@pytest.mark.asyncio
async def test_role_validation_and_conflicts(api_client: httpx.AsyncClient) -> None:
    bad = await api_client.post("/api/settings/roles", json={"name": "", "focus": "x", "bias": "y"})
    assert bad.status_code == 422

    first = (
        await api_client.post(
            "/api/settings/roles",
            json={"name": "CFO", "focus": "Runway", "bias": "Protect cash"},
        )
    ).json()
    duplicate = await api_client.post(
        "/api/settings/roles",
        json={"name": "cfo", "focus": "Other", "bias": "Other"},
    )
    assert duplicate.status_code == 409

    missing_role = await api_client.put(
        "/api/settings/roles/00000000-0000-0000-0000-000000000000",
        json={"name": "x", "focus": "y", "bias": "z"},
    )
    assert missing_role.status_code == 404
    delete_missing = await api_client.delete(
        "/api/settings/roles/00000000-0000-0000-0000-000000000000"
    )
    assert delete_missing.status_code == 404
    _ = first  # keep the created role referenced


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 2, 6])
async def test_settings_count_validation(api_client: httpx.AsyncClient, count: int) -> None:
    response = await api_client.patch("/api/settings", json={"default_role_count": count})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_llm_model(api_client: httpx.AsyncClient) -> None:
    updated = (await api_client.patch("/api/settings", json={"llm_model": "openai/gpt-4o"})).json()
    assert updated["llm_model"] == "openai/gpt-4o"

    empty = await api_client.patch("/api/settings", json={"llm_model": "   "})
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_list_models(api_client: httpx.AsyncClient) -> None:
    models = (await api_client.get("/api/models")).json()
    assert len(models) >= 1
    assert all("id" in model and "name" in model for model in models)

    zdr = (await api_client.get("/api/models?zdr=true")).json()
    assert len(zdr) >= 1
    assert len(zdr) <= len(models)


@pytest.mark.asyncio
async def test_library_run_requires_enough_saved_roles(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/runs",
        json={"decision": "Use saved roles", "debate": False, "role_source": "library"},
    )
    assert response.status_code == 409
    assert "at least 3" in response.json()["detail"]


@pytest.mark.asyncio
async def test_library_run_uses_backend_selected_roles(api_client: httpx.AsyncClient) -> None:
    roles_payload = [
        {"name": "Strategist", "focus": "Long-term positioning", "bias": "Prefer optionality"},
        {"name": "Operator", "focus": "Execution risk", "bias": "Prefer simplicity"},
        {"name": "Skeptic", "focus": "Disconfirming evidence", "bias": "Default to no"},
    ]
    for role in roles_payload:
        created = await api_client.post("/api/settings/roles", json=role)
        assert created.status_code == 201

    response = await api_client.post(
        "/api/runs",
        json={"decision": "Use saved roles", "debate": False, "role_source": "library"},
    )
    assert response.status_code == 202
    record = await wait_for_terminal(api_client, response.json()["id"])
    assert record["status"] == "completed"
    assert [role["name"] for role in record["roles"]] == [
        "Strategist",
        "Operator",
        "Skeptic",
    ]


@pytest.mark.asyncio
async def test_run_rejects_client_supplied_roles(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/runs",
        json={
            "decision": "Spoof roles",
            "roles": [
                {"name": "A", "focus": "focus", "bias": "bias"},
                {"name": "B", "focus": "focus", "bias": "bias"},
                {"name": "C", "focus": "focus", "bias": "bias"},
            ],
        },
    )
    assert response.status_code == 422
