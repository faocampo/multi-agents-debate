import { beforeEach, describe, expect, it, vi } from "vitest";
import { createRun, deleteRole } from "../api";

describe("api", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("accepts a successful 204 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(deleteRole("role-1")).resolves.toBeUndefined();
  });

  it("requests a backend-selected library panel without sending role definitions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "run-1" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createRun("Decide", true, "library");

    const request = fetchMock.mock.calls[0];
    expect(request).toBeDefined();
    const body = JSON.parse(request![1]?.body as string) as Record<string, unknown>;
    expect(body).toEqual({ decision: "Decide", debate: true, clarify: false, role_source: "library" });
    expect(body).not.toHaveProperty("roles");
  });
});
