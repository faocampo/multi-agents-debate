import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ClarificationForm } from "../components/ClarificationForm";
import { submitClarification } from "../api";

vi.mock("../api", () => ({ submitClarification: vi.fn() }));

const submitMock = vi.mocked(submitClarification);

describe("ClarificationForm", () => {
  beforeEach(() => {
    submitMock.mockReset();
    submitMock.mockResolvedValue(undefined);
  });

  it("submits each answer for the matching question", () => {
    render(<ClarificationForm runId="run-1" questions={["What matters?", "Who is affected?"]} />);

    const answers = screen.getAllByRole("textbox");
    fireEvent.change(answers[0]!, { target: { value: "Safety" } });
    fireEvent.change(answers[1]!, { target: { value: "Customers" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(submitMock).toHaveBeenCalledWith("run-1", {
      answers: ["Safety", "Customers"],
      skipped: false,
    });
  });

  it("can skip the questions without answers", () => {
    render(<ClarificationForm runId="run-1" questions={["What matters?"]} />);

    fireEvent.click(screen.getByRole("button", { name: /skip/i }));

    expect(submitMock).toHaveBeenCalledWith("run-1", { answers: [], skipped: true });
  });
});
