import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Settings } from "../components/Settings";

const MODELS = [{ id: "openai/gpt-4o-mini", name: "GPT-4o Mini" }];

function settingsResponse(default_role_count = 3, llm_model: string | null = "openai/gpt-4o-mini") {
  return new Response(
    JSON.stringify({ default_role_count, llm_model, roles: [] }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

function modelsResponse(models = MODELS) {
  return new Response(JSON.stringify(models), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function extractUrl(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input.toString();
}

function defaultFetchMock(
  overrides: { settings?: Response; models?: Response } = {},
): typeof vi.fn {
  const settings = overrides.settings ?? settingsResponse();
  const models = overrides.models ?? modelsResponse();
  return vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = extractUrl(input);
    if (url.includes("/api/models")) return Promise.resolve(models);
    return Promise.resolve(settings);
  });
}

describe("Settings", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads settings and renders the default role count picker", async () => {
    vi.stubGlobal("fetch", defaultFetchMock({ settings: settingsResponse(4) }));

    render(<Settings onBack={() => {}} />);

    expect(await screen.findByRole("heading", { name: /agent roles library/i })).toBeVisible();
    const four = screen.getByRole("radio", { name: "4" });
    expect(four).toHaveAttribute("aria-checked", "true");
  });

  it("creates a role via the form", async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/settings/roles") && init?.method === "POST") {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        return Promise.resolve(
          new Response(
            JSON.stringify({ id: "role-1", name: body.name, focus: body.focus, bias: body.bias, prompt: body.prompt ?? null }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (url.includes("/api/models")) return Promise.resolve(modelsResponse());
      return Promise.resolve(settingsResponse());
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Settings onBack={() => {}} />);

    await screen.findByRole("heading", { name: /agent roles library/i });

    fireEvent.change(screen.getByPlaceholderText("Customer Advocate"), { target: { value: "Engineer" } });
    fireEvent.change(screen.getByPlaceholderText(/responsible for analyzing/i), { target: { value: "Delivery risk" } });
    fireEvent.change(screen.getByPlaceholderText(/deliberate perspective/i), { target: { value: "Ship safely" } });

    fireEvent.click(screen.getByRole("button", { name: /add role/i }));

    await waitFor(() => {
      expect(screen.getByText("Engineer")).toBeVisible();
    });

    const calls = fetchMock.mock.calls.filter(
      ([url]) => typeof url === "string" && url.endsWith("/api/settings/roles"),
    );
    expect(calls.length).toBeGreaterThanOrEqual(1);
  });

  it("confirms deletion and removes a role after a 204", async () => {
    const role = {
      id: "role-1",
      name: "Engineer",
      focus: "Delivery",
      bias: "Ship safely",
      prompt: null,
    };
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = extractUrl(input);
      if (init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.includes("/api/models")) return Promise.resolve(modelsResponse());
      return Promise.resolve(
        new Response(JSON.stringify({ default_role_count: 3, llm_model: "openai/gpt-4o-mini", roles: [role] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Settings onBack={() => {}} />);
    await screen.findByText("Engineer");

    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    expect(screen.getByRole("button", { name: /confirm delete/i })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));

    await waitFor(() => expect(screen.queryByText("Engineer")).not.toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a conflict error on 409", async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/settings/roles") && init?.method === "POST") {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "A role with that name already exists." }), {
            status: 409,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (url.includes("/api/models")) return Promise.resolve(modelsResponse());
      return Promise.resolve(settingsResponse());
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Settings onBack={() => {}} />);
    await screen.findByRole("heading", { name: /agent roles library/i });

    fireEvent.change(screen.getByPlaceholderText("Customer Advocate"), { target: { value: "Engineer" } });
    fireEvent.change(screen.getByPlaceholderText(/responsible for analyzing/i), { target: { value: "Delivery" } });
    fireEvent.change(screen.getByPlaceholderText(/deliberate perspective/i), { target: { value: "Ship" } });
    fireEvent.click(screen.getByRole("button", { name: /add role/i }));

    await waitFor(() => {
      expect(screen.getByText(/already exists/i)).toBeVisible();
    });
  });

  it("loads and selects a model", async () => {
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/settings") && init?.method === "PATCH") {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        return Promise.resolve(
          settingsResponse(3, body.llm_model as string | null),
        );
      }
      if (url.includes("/api/models")) {
        return Promise.resolve(modelsResponse([
          { id: "openai/gpt-4o-mini", name: "GPT-4o Mini" },
          { id: "anthropic/claude-sonnet", name: "Claude Sonnet" },
        ]));
      }
      return Promise.resolve(settingsResponse());
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Settings onBack={() => {}} />);
    await screen.findByRole("heading", { name: /agent roles library/i });

    const select = screen.getByLabelText("Model") as HTMLSelectElement;
    await waitFor(() => {
      expect(select.value).toBe("openai/gpt-4o-mini");
    });

    fireEvent.change(select, { target: { value: "anthropic/claude-sonnet" } });

    await waitFor(() => {
      expect(select.value).toBe("anthropic/claude-sonnet");
    });

    const patchCalls = fetchMock.mock.calls.filter(
      ([url, init]) =>
        typeof url === "string" && url.endsWith("/api/settings") && (init as RequestInit | undefined)?.method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThanOrEqual(1);
    const init = patchCalls[0]?.[1] as RequestInit | undefined;
    expect(init).toBeDefined();
    const body = JSON.parse(init!.body as string) as Record<string, unknown>;
    expect(body.llm_model).toBe("anthropic/claude-sonnet");
  });
});
