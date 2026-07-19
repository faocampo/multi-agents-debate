import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Settings } from "../components/Settings";

describe("Settings", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads settings and renders the default role count picker", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ default_role_count: 4, roles: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

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
      return Promise.resolve(
        new Response(
          JSON.stringify({ default_role_count: 3, roles: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Settings onBack={() => {}} />);

    await screen.findByRole("heading", { name: /agent roles library/i });

    fireEvent.change(screen.getByPlaceholderText("Customer Advocate"), { target: { value: "Engineer" } });
    fireEvent.change(screen.getByPlaceholderText(/responsible for analyzing/i), { target: { value: "Delivery risk" } });
    fireEvent.change(screen.getByPlaceholderText(/deliberate perspective/i), { target: { value: "Ship safely" } });

    const submit = screen.getByRole("button", { name: /add role/i });
    fireEvent.click(submit);

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
    const fetchMock = vi.fn().mockImplementation((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(
        new Response(JSON.stringify({ default_role_count: 3, roles: [role] }), {
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
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.endsWith("/api/settings/roles") && init?.method === "POST") {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: "A role with that name already exists." }), {
              status: 409,
              headers: { "Content-Type": "application/json" },
            }),
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({ default_role_count: 3, roles: [] }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }),
    );

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
});
