from __future__ import annotations

import json

from app.models import RoleSpec
from app.prompts import (
    advocate_prompt,
    debate_prompt,
    expert_prompt,
    role_planner_prompt,
    synthesis_prompt,
)


def role(name: str) -> RoleSpec:
    return RoleSpec(name=name, focus=f"{name} focus", bias=f"{name} bias")


def test_role_planner_count_is_a_trusted_system_instruction() -> None:
    system, user = role_planner_prompt("Decide", desired_role_count=4)

    assert "exactly 4 roles" in system
    assert set(json.loads(user)) == {"decision"}


def test_expert_prompt_contains_only_decision_and_own_role() -> None:
    _, user = expert_prompt("Choose café safely", role("Engineer"))

    payload = json.loads(user)
    assert set(payload) == {"decision", "role"}
    assert payload["decision"] == "Choose café safely"
    assert payload["role"]["name"] == "Engineer"
    assert "Finance" not in user


def test_debate_prompt_contains_self_and_every_opponent_once() -> None:
    _, user = debate_prompt(
        "Decide",
        role("Engineer"),
        "Initial engineering view",
        [(role("Finance"), "Finance view"), (role("Customer"), "Customer view")],
    )

    payload = json.loads(user)
    assert payload["original_opinion"] == "Initial engineering view"
    assert [item["role"]["name"] for item in payload["opposing_opinions"]] == [
        "Finance",
        "Customer",
    ]


def test_advocate_and_synthesis_receive_the_active_round() -> None:
    active = [(role("Engineer"), "Updated engineering view")]
    _, advocate_user = advocate_prompt("Decide", round_name="rebuttal", active_opinions=active)
    _, synthesis_user = synthesis_prompt(
        "Decide",
        round_name="rebuttal",
        active_opinions=active,
        devils_advocate="Stress test",
    )

    advocate_payload = json.loads(advocate_user)
    synthesis_payload = json.loads(synthesis_user)
    assert advocate_payload["active_opinions"][0]["analysis"] == "Updated engineering view"
    assert synthesis_payload["active_opinions"] == advocate_payload["active_opinions"]
    assert synthesis_payload["devils_advocate"] == "Stress test"
