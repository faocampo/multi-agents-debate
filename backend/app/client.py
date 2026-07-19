from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx

from .config import Settings
from .models import LLMModelInfo


class LLMClient(Protocol):
    async def complete(
        self, system: str, user: str, temperature: float, model: str | None = None
    ) -> str:
        """Return one non-empty assistant completion."""

    async def list_models(self, zdr: bool = False) -> list[LLMModelInfo]:
        """Return available text-capable models from the provider."""


class ProviderError(Exception):
    retryable = False


class ProviderTimeout(ProviderError):
    retryable = True


class ProviderHTTPError(ProviderError):
    def __init__(self, *, status_code: int | None, retryable: bool) -> None:
        super().__init__("provider HTTP request failed")
        self.status_code = status_code
        self.retryable = retryable


class ProviderProtocolError(ProviderError):
    pass


class HttpxLLMClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.llm_timeout_seconds)
        )

    async def complete(
        self, system: str, user: str, temperature: float, model: str | None = None
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self._settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        try:
            async with asyncio.timeout(self._settings.llm_timeout_seconds):
                response = await self._client.post(
                    f"{self._settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.llm_api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderTimeout("provider request timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderHTTPError(status_code=None, retryable=True) from exc

        if not response.is_success:
            retryable = response.status_code in {408, 429} or response.status_code >= 500
            raise ProviderHTTPError(status_code=response.status_code, retryable=retryable)

        try:
            body = response.json()
            choices = body["choices"]
            content = choices[0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderProtocolError("provider returned an invalid response") from exc

        if not isinstance(content, str) or not content.strip():
            raise ProviderProtocolError("provider returned empty content")
        return content.strip()

    async def list_models(self, zdr: bool = False) -> list[LLMModelInfo]:
        zdr_ids: set[str] = set()
        if zdr:
            zdr_ids = await self._zdr_model_ids()

        response = await self._provider_get(f"{self._settings.llm_base_url}/models")
        try:
            body = response.json()
            data = body["data"]
            if not isinstance(data, list):
                raise ProviderProtocolError("provider returned an invalid models response")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderProtocolError("provider returned an invalid models response") from exc

        models: list[LLMModelInfo] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            if zdr and model_id not in zdr_ids:
                continue
            if not self._is_text_capable(item):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                name = model_id
            description = item.get("description")
            if not isinstance(description, str):
                description = None
            models.append(LLMModelInfo(id=model_id, name=name, description=description))
        models.sort(key=lambda model: model.name.lower())
        return models

    async def _zdr_model_ids(self) -> set[str]:
        response = await self._provider_get(f"{self._settings.llm_base_url}/endpoints/zdr")
        try:
            body = response.json()
            data = body["data"]
            if not isinstance(data, list):
                raise ProviderProtocolError("provider returned an invalid ZDR response")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderProtocolError("provider returned an invalid ZDR response") from exc

        ids: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            model_id = item.get("model_id")
            if isinstance(model_id, str) and model_id.strip():
                ids.add(model_id)
        return ids

    async def _provider_get(self, url: str) -> httpx.Response:
        try:
            async with asyncio.timeout(self._settings.llm_timeout_seconds):
                response = await self._client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._settings.llm_api_key.get_secret_value()}"
                    },
                )
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ProviderTimeout("provider request timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderHTTPError(status_code=None, retryable=True) from exc

        if not response.is_success:
            retryable = response.status_code in {408, 429} or response.status_code >= 500
            raise ProviderHTTPError(status_code=response.status_code, retryable=retryable)
        return response

    @staticmethod
    def _is_text_capable(item: dict[str, Any]) -> bool:
        architecture = item.get("architecture")
        if not isinstance(architecture, dict):
            return True
        input_modalities = architecture.get("input_modalities")
        if isinstance(input_modalities, list):
            return any("text" in str(modality).lower() for modality in input_modalities)
        modality = architecture.get("modality")
        if isinstance(modality, str):
            input_side = modality.split("->")[0] if "->" in modality else modality
            return "text" in input_side.lower()
        return True

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
