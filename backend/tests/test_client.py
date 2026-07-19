from __future__ import annotations

import json

import httpx
import pytest

from app.client import (
    HttpxLLMClient,
    ProviderHTTPError,
    ProviderProtocolError,
    ProviderTimeout,
)
from app.config import Settings


def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_base_url="http://provider.test/v1",
        llm_api_key="secret",
        llm_model="test-model",
        llm_timeout_seconds=2,
    )


@pytest.mark.asyncio
async def test_client_sends_openai_compatible_request() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://provider.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        payload = json.loads(request.content)
        assert payload == {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            "temperature": 0.7,
            "stream": False,
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": " done "}}]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxLLMClient(settings(), http_client)

    assert await client.complete("system", "user", 0.7) == "done"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_client_uses_model_override() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "override-model"
        return httpx.Response(200, json={"choices": [{"message": {"content": " done "}}]})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxLLMClient(settings(), http_client)

    assert await client.complete("system", "user", 0.7, model="override-model") == "done"
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "retryable"),
    [(400, False), (429, True), (503, True)],
)
async def test_client_maps_http_errors(status: int, retryable: bool) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status))
    http_client = httpx.AsyncClient(transport=transport)
    client = HttpxLLMClient(settings(), http_client)

    with pytest.raises(ProviderHTTPError) as captured:
        await client.complete("system", "user", 0.4)
    assert captured.value.retryable is retryable
    await http_client.aclose()


@pytest.mark.asyncio
async def test_client_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxLLMClient(settings(), http_client)

    with pytest.raises(ProviderTimeout):
        await client.complete("system", "user", 0.4)
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": " "}}]},
    ],
)
async def test_client_rejects_invalid_provider_payloads(body: object) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    http_client = httpx.AsyncClient(transport=transport)
    client = HttpxLLMClient(settings(), http_client)

    with pytest.raises(ProviderProtocolError):
        await client.complete("system", "user", 0.4)
    await http_client.aclose()


@pytest.mark.asyncio
async def test_list_models_filters_text_and_sorts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://provider.test/v1/models"
        body = {
            "data": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "architecture": {"modality": "text->text"},
                },
                {
                    "id": "audio/audio-model",
                    "name": "Audio Model",
                    "architecture": {"modality": "audio->audio"},
                },
                {
                    "id": "anthropic/claude-sonnet",
                    "name": "Claude Sonnet",
                    "architecture": {"input_modalities": ["text", "image"]},
                },
            ]
        }
        return httpx.Response(200, json=body)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxLLMClient(settings(), http_client)

    models = await client.list_models()
    assert [model.id for model in models] == [
        "anthropic/claude-sonnet",
        "openai/gpt-4",
    ]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_list_models_zdr_filters_by_endpoints_zdr() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == "http://provider.test/v1/endpoints/zdr":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"model_id": "openai/gpt-4", "model_name": "GPT-4"},
                    ]
                },
            )
        body = {
            "data": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "architecture": {"modality": "text->text"},
                },
                {
                    "id": "anthropic/claude-sonnet",
                    "name": "Claude Sonnet",
                    "architecture": {"modality": "text->text"},
                },
            ]
        }
        return httpx.Response(200, json=body)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxLLMClient(settings(), http_client)

    models = await client.list_models(zdr=True)
    assert [model.id for model in models] == ["openai/gpt-4"]
    await http_client.aclose()
