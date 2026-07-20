from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .models import RoleSpec, validate_role_panel

_FENCE = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(?P<body>.*?)\r?\n```[ \t]*\Z",
    flags=re.DOTALL | re.IGNORECASE,
)


class MalformedRoles(ValueError):
    pass


class MalformedClarification(ValueError):
    pass


def parse_clarifying_questions(raw: str, *, max_questions: int = 5) -> list[str]:
    try:
        decoded: Any = json.loads(raw.strip())
    except (json.JSONDecodeError, TypeError) as exc:
        raise MalformedClarification("clarifying questions are not valid JSON") from exc
    if not isinstance(decoded, list) or not 1 <= len(decoded) <= max_questions:
        raise MalformedClarification("clarifying questions must contain one to five strings")
    questions = [item.strip() for item in decoded if isinstance(item, str)]
    if len(questions) != len(decoded) or any(not question for question in questions):
        raise MalformedClarification("clarifying questions must be non-empty strings")
    if len({question.casefold() for question in questions}) != len(questions):
        raise MalformedClarification("clarifying questions must be unique")
    if any(len(question) > 500 for question in questions):
        raise MalformedClarification("clarifying questions must be 500 characters or fewer")
    return questions


def parse_roles(raw: str, *, expected_count: int | None = None) -> list[RoleSpec]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        match = _FENCE.fullmatch(candidate)
        if match is None:
            raise MalformedRoles("role response contains an invalid code fence")
        candidate = match.group("body").strip()

    try:
        decoded: Any = json.loads(candidate)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MalformedRoles("role response is not valid JSON") from exc

    if not isinstance(decoded, list):
        raise MalformedRoles("role response must be an array of three to five roles")

    try:
        roles = validate_role_panel(
            [RoleSpec.model_validate(item, strict=True) for item in decoded]
        )
    except (ValidationError, ValueError) as exc:
        raise MalformedRoles("role response contains an invalid role panel") from exc
    if expected_count is not None and len(roles) != expected_count:
        raise MalformedRoles(f"role response must contain exactly {expected_count} roles")
    return roles
