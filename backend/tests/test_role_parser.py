from __future__ import annotations

import json

import pytest

from app.role_parser import (
    MalformedClarification,
    MalformedRoles,
    parse_clarifying_questions,
    parse_roles,
)
from tests.fakes import ROLES


@pytest.mark.parametrize(
    "payload",
    [json.dumps(ROLES), f"```json\n{json.dumps(ROLES)}\n```"],
)
def test_parse_valid_role_arrays(payload: str) -> None:
    roles = parse_roles(payload)

    assert [role.name for role in roles] == [role["name"] for role in ROLES]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps(ROLES[:2]),
        json.dumps(ROLES + ROLES),
        json.dumps({"roles": ROLES}),
        json.dumps([{"name": "Only", "focus": "One"}] * 3),
        json.dumps([{**role, "extra": "forbidden"} for role in ROLES]),
        json.dumps([{**role, "name": 12} for role in ROLES]),
        json.dumps([ROLES[0], ROLES[0], ROLES[2]]),
        f"before\n{json.dumps(ROLES)}",
        f"```json\n{json.dumps(ROLES)}\n```\nafter",
    ],
)
def test_rejects_malformed_roles(payload: str) -> None:
    with pytest.raises(MalformedRoles):
        parse_roles(payload)


def test_rejects_a_panel_that_does_not_match_the_expected_count() -> None:
    with pytest.raises(MalformedRoles):
        parse_roles(json.dumps(ROLES), expected_count=4)


def test_rejects_names_that_only_differ_by_case_and_whitespace() -> None:
    payload = [*ROLES]
    payload[1] = {**payload[1], "name": "  customer   advocate  "}

    with pytest.raises(MalformedRoles):
        parse_roles(json.dumps(payload))


@pytest.mark.parametrize(
    "payload",
    [json.dumps(["What is the target outcome?", "Who is most affected?"])],
)
def test_parse_valid_clarifying_questions(payload: str) -> None:
    assert parse_clarifying_questions(payload) == [
        "What is the target outcome?",
        "Who is most affected?",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps([]),
        json.dumps(["one"] * 6),
        json.dumps(["", "valid"]),
        json.dumps(["same", "same"]),
        json.dumps({"questions": ["one"]}),
        json.dumps([1, "valid"]),
    ],
)
def test_rejects_malformed_clarifying_questions(payload: str) -> None:
    with pytest.raises(MalformedClarification):
        parse_clarifying_questions(payload)
