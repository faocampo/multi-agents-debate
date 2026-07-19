from __future__ import annotations

import asyncio
from typing import Any, Protocol

import httpx

from .config import Settings


class LLMClient(Protocol):
    async def complete(self, system: str, user: str, temperature: float) -> str:
        """Return one non-empty assistant completion."""


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

    async def complete(self, system: str, user: str, temperature: float) -> str:
        payload: dict[str, Any] = {
            "model": self._settings.llm_model,
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

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
