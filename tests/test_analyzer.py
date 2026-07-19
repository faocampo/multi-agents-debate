import json
import threading
import unittest

from multi_agent_experts import (
    MultiAgentAnalyzer,
    RolePlanningError,
    SwarmConfig,
)


ROLES = [
    {"name": "Investor", "focus": "near-term return", "bias": "cash now"},
    {"name": "Engineer", "focus": "reliability", "bias": "technical safety"},
    {"name": "User Advocate", "focus": "customer trust", "bias": "user value"},
]


class RecordingClient:
    def __init__(self, role_payload=None):
        self.role_payload = role_payload if role_payload is not None else ROLES
        self.calls = []
        self.lock = threading.Lock()

    def complete(self, system, user, temperature=0.7):
        with self.lock:
            self.calls.append((system, user, temperature))
        if "orchestrate a conflict-driven" in system:
            return "```json\n{}\n```".format(json.dumps(self.role_payload))
        if "second analysis round" in system:
            role = system.split("You are the ", 1)[1].split(" in the", 1)[0]
            return "debated:{}".format(role)
        if "sole job is to attack" in system:
            return "shared assumption attacked"
        if "synthesize a conflict-driven" in system:
            return "conditional final verdict"
        if "strictly from this position" in system:
            role = system.split("You are the ", 1)[1].split(" in a", 1)[0]
            return "initial:{}".format(role)
        raise AssertionError("unexpected prompt")


class MultiAgentAnalyzerTests(unittest.TestCase):
    def test_full_pipeline_preserves_role_order_and_uses_debate(self):
        client = RecordingClient()
        analyzer = MultiAgentAnalyzer(client, SwarmConfig(min_roles=3, max_roles=3))

        result = analyzer.analyze("Should we remove the free tier?")

        self.assertEqual([role.name for role in result.roles], [r["name"] for r in ROLES])
        self.assertEqual(
            [opinion.initial_analysis for opinion in result.opinions],
            ["initial:Investor", "initial:Engineer", "initial:User Advocate"],
        )
        self.assertEqual(
            [opinion.debate_response for opinion in result.opinions],
            ["debated:Investor", "debated:Engineer", "debated:User Advocate"],
        )
        self.assertEqual(result.devils_advocate, "shared assumption attacked")
        self.assertEqual(result.synthesis, "conditional final verdict")
        self.assertTrue(result.debate_used)

        debate_calls = [call for call in client.calls if "second analysis round" in call[0]]
        self.assertEqual(len(debate_calls), 3)
        investor_debate = next(call for call in debate_calls if "Investor" in call[0])
        self.assertNotIn("initial:Investor", investor_debate[1])
        self.assertIn("initial:Engineer", investor_debate[1])
        self.assertIn("initial:User Advocate", investor_debate[1])

    def test_debate_can_be_disabled_per_run(self):
        client = RecordingClient()
        analyzer = MultiAgentAnalyzer(client, SwarmConfig(min_roles=3, max_roles=3))

        result = analyzer.analyze("Decision", debate=False)

        self.assertFalse(result.debate_used)
        self.assertTrue(all(opinion.debate_response is None for opinion in result.opinions))
        self.assertFalse(any("second analysis round" in call[0] for call in client.calls))

    def test_rejects_duplicate_roles(self):
        duplicate_roles = [ROLES[0], dict(ROLES[0]), ROLES[2]]
        analyzer = MultiAgentAnalyzer(
            RecordingClient(duplicate_roles),
            SwarmConfig(min_roles=3, max_roles=3),
        )

        with self.assertRaises(RolePlanningError):
            analyzer.plan_roles("Decision")

    def test_rejects_wrong_role_count(self):
        analyzer = MultiAgentAnalyzer(
            RecordingClient(ROLES[:2]),
            SwarmConfig(min_roles=3, max_roles=3),
        )

        with self.assertRaises(RolePlanningError):
            analyzer.plan_roles("Decision")


if __name__ == "__main__":
    unittest.main()
