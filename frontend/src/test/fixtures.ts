import type { RunRecord } from "../types";

export const completedRun: RunRecord = {
  id: "c60c3906-c14b-4b9a-ad9a-2f215bbac10b",
  decision: "Should we launch a reversible pilot?",
  debate: true,
  clarify: false,
  status: "completed",
  stage: "completed",
  created_at: "2026-07-19T12:00:00.000Z",
  started_at: "2026-07-19T12:00:01.000Z",
  completed_at: "2026-07-19T12:01:00.000Z",
  clarifying_questions: [],
  clarifying_answers: null,
  clarification_skipped: false,
  roles: [
    { name: "Customer", focus: "Adoption", bias: "Prefer usability" },
    { name: "Finance", focus: "Economics", bias: "Protect runway" },
    { name: "Engineer", focus: "Delivery", bias: "Prefer reversibility" },
  ],
  expert_opinions: [
    {
      role: { name: "Customer", focus: "Adoption", bias: "Prefer usability" },
      initial_analysis: "## Recommendation\n\nPilot with customers.",
      initial_completed_at: "2026-07-19T12:00:10.000Z",
      rebuttal: "## Revised recommendation\n\nKeep the pilot small.",
      rebuttal_completed_at: "2026-07-19T12:00:30.000Z",
    },
  ],
  advocate_analysis: "## Shared assumptions under attack\n\nDemand may move.",
  synthesis: "## Verdict\n\nRun the pilot.",
  error: null,
};

