import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { completedRun } from "./fixtures";

class FakeEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  close = vi.fn();
}

describe("App", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
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

  it("scrolls to the expert panel after starting a regular analysis", async () => {
    const scrolledIds: string[] = [];
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(function (this: HTMLElement) {
        scrolledIds.push(this.id);
      }),
    });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    });
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/settings") {
          return Promise.resolve(new Response(JSON.stringify({ default_role_count: 3, roles: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
        }
        if (url === "/api/runs?limit=20") {
          return Promise.resolve(new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
        }
        if (url === "/api/runs" && init?.method === "POST") {
          return Promise.resolve(new Response(JSON.stringify({
            id: "run-1",
            decision_excerpt: "Should we run a pilot?",
            debate: true,
            status: "queued",
            stage: "queued",
            role_count: 0,
            created_at: completedRun.created_at,
            completed_at: null,
            root_run_id: null,
            parent_run_id: null,
          }), {
            status: 202,
            headers: { "Content-Type": "application/json" },
          }));
        }
        if (url === "/api/runs/run-1") {
          return Promise.resolve(new Response(JSON.stringify({
            ...completedRun,
            id: "run-1",
            decision: "Should we run a pilot?",
            status: "running",
            stage: "independent_analysis",
            completed_at: null,
            synthesis: null,
          }), {
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
    fireEvent.change(await screen.findByLabelText("Decision to analyze"), {
      target: { value: "Should we run a pilot?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze decision/i }));

    await screen.findByRole("heading", { name: "3 independent lenses" });
    await waitFor(() => expect(scrolledIds).toContain("panel"));
  });

  it("scrolls to clarifying questions when they are the next required action", async () => {
    const scrolledIds: string[] = [];
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(function (this: HTMLElement) {
        scrolledIds.push(this.id);
      }),
    });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    });
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/settings") {
          return Promise.resolve(new Response(JSON.stringify({ default_role_count: 3, roles: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
        }
        if (url === "/api/runs?limit=20") {
          return Promise.resolve(new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
        }
        if (url === "/api/runs" && init?.method === "POST") {
          return Promise.resolve(new Response(JSON.stringify({
            id: "run-clarify",
            decision_excerpt: "Should we run a pilot?",
            debate: true,
            status: "queued",
            stage: "queued",
            role_count: 0,
            created_at: completedRun.created_at,
            completed_at: null,
            root_run_id: null,
            parent_run_id: null,
          }), {
            status: 202,
            headers: { "Content-Type": "application/json" },
          }));
        }
        if (url === "/api/runs/run-clarify") {
          return Promise.resolve(new Response(JSON.stringify({
            ...completedRun,
            id: "run-clarify",
            decision: "Should we run a pilot?",
            clarify: true,
            status: "running",
            stage: "awaiting_clarification",
            completed_at: null,
            roles: [],
            expert_opinions: [],
            advocate_analysis: null,
            synthesis: null,
            clarifying_questions: ["What outcome matters most?"],
          }), {
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
    fireEvent.change(await screen.findByLabelText("Decision to analyze"), {
      target: { value: "Should we run a pilot?" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /Ask clarifying questions first/i }));
    fireEvent.click(screen.getByRole("button", { name: /Analyze decision/i }));

    await screen.findByText("What outcome matters most?");
    await waitFor(() => expect(scrolledIds).toContain("clarification"));
  });
});
