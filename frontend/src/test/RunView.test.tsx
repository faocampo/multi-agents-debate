import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunView } from "../components/RunView";
import { completedRun } from "./fixtures";

describe("RunView", () => {
  it("keeps answered clarifying questions visible as a collapsible summary", () => {
    render(
      <RunView
        run={{
          ...completedRun,
          clarify: true,
          clarifying_questions: ["What outcome matters most?", "Who is affected?"],
          clarifying_answers: ["Safety", "Customers and operators"],
        }}
        connection="closed"
        challengeSubmitting={false}
        challengeError={null}
        onChallenge={vi.fn()}
      />,
    );

    expect(screen.getByText("2 answered questions")).toBeVisible();
    expect(screen.getByText("What outcome matters most?")).toBeVisible();
    expect(screen.getByText("Safety")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Continue to role planning/i })).not.toBeInTheDocument();
  });
});
