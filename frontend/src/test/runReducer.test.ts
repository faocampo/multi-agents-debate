import { describe, expect, it } from "vitest";
import { applyRunEvent } from "../runReducer";
import type { RunEvent } from "../types";
import { completedRun } from "./fixtures";

describe("applyRunEvent", () => {
  it("applies clarification request and answer events", () => {
    const run = { ...completedRun, clarify: true, status: "running" as const, stage: "awaiting_clarification" as const };
    const requested = applyRunEvent(run, {
      id: 1,
      run_id: run.id,
      type: "clarification.requested",
      timestamp: "2026-07-19T12:00:01.000Z",
      data: { questions: ["What matters most?"] },
    });
    const answered = applyRunEvent(requested, {
      id: 2,
      run_id: run.id,
      type: "clarification.answered",
      timestamp: "2026-07-19T12:00:02.000Z",
      data: { answers: ["Safety"], skipped: false },
    });

    expect(requested.clarifying_questions).toEqual(["What matters most?"]);
    expect(answered.clarifying_answers).toEqual(["Safety"]);
    expect(answered.clarification_skipped).toBe(false);
  });

  it("applies out-of-order expert completion in canonical role order", () => {
    const run = { ...completedRun, status: "running" as const, stage: "independent_analysis" as const, expert_opinions: [] };
    const engineer = completedRun.roles[2]!;
    const customer = completedRun.roles[0]!;
    const baseEvent = {
      id: 1,
      run_id: run.id,
      type: "expert.completed" as const,
      timestamp: "2026-07-19T12:00:10.000Z",
    };

    const afterEngineer = applyRunEvent(run, {
      ...baseEvent,
      data: {
        opinion: {
          role: engineer,
          initial_analysis: "Engineer view",
          initial_completed_at: baseEvent.timestamp,
          rebuttal: null,
          rebuttal_completed_at: null,
          advocate_response: null,
          advocate_response_completed_at: null,
        },
      },
    });
    const afterCustomer = applyRunEvent(afterEngineer, {
      ...baseEvent,
      id: 2,
      data: {
        opinion: {
          role: customer,
          initial_analysis: "Customer view",
          initial_completed_at: baseEvent.timestamp,
          rebuttal: null,
          rebuttal_completed_at: null,
          advocate_response: null,
          advocate_response_completed_at: null,
        },
      },
    });

    expect(afterCustomer.expert_opinions.map((opinion) => opinion.role.name)).toEqual([
      "Customer",
      "Engineer",
    ]);
  });

  it("retains content when applying a terminal failure", () => {
    const event: RunEvent = {
      id: 8,
      run_id: completedRun.id,
      type: "run.failed",
      timestamp: "2026-07-19T12:00:50.000Z",
      data: {
        error: {
          stage: "synthesis",
          code: "provider_timeout",
          message: "Timed out",
          retryable: true,
        },
        summary: {
          id: completedRun.id,
          decision_excerpt: completedRun.decision,
          debate: true,
          status: "failed",
          stage: "failed",
          role_count: 3,
          created_at: completedRun.created_at,
          completed_at: "2026-07-19T12:00:50.000Z",
          root_run_id: null,
          parent_run_id: null,
        },
      },
    };

    const result = applyRunEvent({ ...completedRun, status: "running", stage: "synthesis" }, event);
    expect(result.status).toBe("failed");
    expect(result.expert_opinions).toEqual(completedRun.expert_opinions);
    expect(result.error?.stage).toBe("synthesis");
  });

  it("applies challenge events to the child run", () => {
    const run = {
      ...completedRun,
      status: "running" as const,
      stage: "challenge_reconsideration" as const,
      expert_opinions: [],
      challenge: {
        kind: "challenge" as const,
        input: "What if demand is lower?",
        parent_run_id: completedRun.id,
        root_run_id: completedRun.id,
        parent_conclusion: completedRun.synthesis!,
      },
    };
    const role = completedRun.roles[0]!;
    const reconsidered = applyRunEvent(run, {
      id: 10,
      run_id: run.id,
      type: "challenge.reconsideration_completed",
      timestamp: "2026-07-19T12:02:10.000Z",
      data: {
        opinion: {
          role,
          initial_analysis: "Reconsidered",
          initial_completed_at: "2026-07-19T12:02:10.000Z",
          rebuttal: null,
          rebuttal_completed_at: null,
          advocate_response: null,
          advocate_response_completed_at: null,
        },
      },
    });
    const debated = applyRunEvent(reconsidered, {
      id: 11,
      run_id: run.id,
      type: "challenge.peer_debate_completed",
      timestamp: "2026-07-19T12:02:20.000Z",
      data: {
        role_name: role.name,
        response: "Peer debate response",
        completed_at: "2026-07-19T12:02:20.000Z",
      },
    });
    const answered = applyRunEvent(debated, {
      id: 12,
      run_id: run.id,
      type: "challenge.advocate_response_completed",
      timestamp: "2026-07-19T12:02:30.000Z",
      data: {
        role_name: role.name,
        response: "Advocate answer",
        completed_at: "2026-07-19T12:02:30.000Z",
      },
    });

    expect(answered.expert_opinions[0]?.initial_analysis).toBe("Reconsidered");
    expect(answered.expert_opinions[0]?.rebuttal).toBe("Peer debate response");
    expect(answered.expert_opinions[0]?.advocate_response).toBe("Advocate answer");
  });
});
