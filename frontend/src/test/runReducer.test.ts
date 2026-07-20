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
        },
      },
    };

    const result = applyRunEvent({ ...completedRun, status: "running", stage: "synthesis" }, event);
    expect(result.status).toBe("failed");
    expect(result.expert_opinions).toEqual(completedRun.expert_opinions);
    expect(result.error?.stage).toBe("synthesis");
  });
});

