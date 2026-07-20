import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        const body = url.includes("/api/settings") && !url.includes("/roles")
          ? JSON.stringify({ default_role_count: 3, roles: [] })
          : JSON.stringify([]);
        return Promise.resolve(
          new Response(body, {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );
  });

  it("renders the empty session and validates submission state", async () => {
    render(<App />);

    expect(await screen.findByText("Your analyses will stay here until the server restarts.")).toBeVisible();
    const button = screen.getByRole("button", { name: /Analyze decision/i });
    const decision = screen.getByLabelText("Decision to analyze");
    expect(button).toBeDisabled();

    fireEvent.change(decision, { target: { value: "Should we run a pilot?" } });
    expect(button).toBeEnabled();

    fireEvent.change(decision, { target: { value: "x".repeat(20_001) } });
    expect(button).toBeDisabled();
    expect(decision).toHaveAttribute("aria-invalid", "true");
  });

  it("defaults expert debate to enabled and clarification to optional", async () => {
    render(<App />);
    await screen.findByText("Your analyses will stay here until the server restarts.");
    expect(screen.getByRole("checkbox", { name: /Include expert debate/i })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Ask clarifying questions first/i })).not.toBeChecked();
  });

  it("refreshes the role library when returning through header navigation", async () => {
    let settingsRequests = 0;
    const roles = ["A", "B", "C"].map((name) => ({
      id: `role-${name}`,
      name,
      focus: `${name} focus`,
      bias: `${name} bias`,
      prompt: null,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/api/settings")) {
          settingsRequests += 1;
          const body = settingsRequests >= 3
            ? { default_role_count: 3, roles }
            : { default_role_count: 3, roles: [] };
          return Promise.resolve(new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
        }
        return Promise.resolve(new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }));
      }),
    );

    render(<App />);
    await screen.findByText("Your analyses will stay here until the server restarts.");
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    await screen.findByRole("heading", { name: /agent roles library/i });
    fireEvent.click(screen.getByRole("button", { name: "Analysis" }));

    expect(await screen.findByRole("checkbox", { name: /use saved roles/i })).toBeEnabled();
  });
});

