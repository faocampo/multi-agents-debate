"""Provider-neutral chat client contracts and an HTTP implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ChatClient(Protocol):
    """Minimal interface required by :class:`MultiAgentAnalyzer`."""

    def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
        """Return one assistant response."""


class ChatClientError(RuntimeError):
    """Raised when a chat provider request or response is invalid."""


@dataclass(frozen=True)
class HTTPChatClient:
    """Client for Ollama and OpenAI-compatible chat endpoints.

    The response format is detected automatically. Both Ollama's
    ``message.content`` and OpenAI's ``choices[0].message.content`` shapes are
    supported.
    """

    endpoint: str
    model: str
    api_key: Optional[str] = None
    timeout: float = 120.0

    def __post_init__(self) -> None:
        if not self.endpoint.strip():
            raise ValueError("endpoint cannot be empty")
        if not self.model.strip():
            raise ValueError("model cannot be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer {}".format(self.api_key)

        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ChatClientError(
                "provider returned HTTP {}: {}".format(exc.code, body[:500])
            ) from exc
        except URLError as exc:
            raise ChatClientError("could not reach provider: {}".format(exc.reason)) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ChatClientError("provider returned invalid JSON") from exc
        return self._extract_content(data)

    @staticmethod
    def _extract_content(data: Any) -> str:
        if not isinstance(data, dict):
            raise ChatClientError("provider response must be a JSON object")
        content: Any = None
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")

        if content is None:
            choices = data.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                choice_message = choices[0].get("message")
                if isinstance(choice_message, dict):
                    content = choice_message.get("content")

        if isinstance(content, list):
            text_parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            content = "".join(text_parts)

        if not isinstance(content, str) or not content.strip():
            raise ChatClientError("provider response did not contain assistant content")
        return content.strip()
