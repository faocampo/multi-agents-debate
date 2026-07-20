import type {
  LLMModelInfo,
  RoleDefinition,
  RoleInput,
  RoleLibrarySettings,
  RoleSource,
  RunRecord,
  RunSummary,
} from "./types";

const API_ROOT = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail[0]?.msg ?? message;
    } catch {
      // Keep the safe status-based message.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export function listRuns(limit = 20): Promise<RunSummary[]> {
  return request(`/api/runs?limit=${limit}`);
}

export function getRun(runId: string): Promise<RunRecord> {
  return request(`/api/runs/${runId}`);
}

export function createRun(
  decision: string,
  debate: boolean,
  roleSource: RoleSource = "planned",
  clarify = false,
): Promise<RunSummary> {
  return request("/api/runs", {
    method: "POST",
    body: JSON.stringify({ decision, debate, clarify, role_source: roleSource }),
  });
}

export function submitClarification(
  runId: string,
  payload: { skipped: boolean; answers: string[] },
): Promise<void> {
  return request(`/api/runs/${runId}/clarification`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runEventsUrl(runId: string): string {
  return `${API_ROOT}/api/runs/${runId}/events`;
}

export function getRoleLibrarySettings(): Promise<RoleLibrarySettings> {
  return request("/api/settings");
}

export function updateSettings(updates: {
  default_role_count?: number;
  llm_model?: string;
}): Promise<RoleLibrarySettings> {
  return request("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export function updateDefaultRoleCount(count: number): Promise<RoleLibrarySettings> {
  return updateSettings({ default_role_count: count });
}

export function listModels(zdr = false): Promise<LLMModelInfo[]> {
  const query = zdr ? "?zdr=true" : "";
  return request(`/api/models${query}`);
}

export function createRole(input: RoleInput): Promise<RoleDefinition> {
  return request("/api/settings/roles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function replaceRole(id: string, input: RoleInput): Promise<RoleDefinition> {
  return request(`/api/settings/roles/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteRole(id: string): Promise<void> {
  return request(`/api/settings/roles/${id}`, { method: "DELETE" });
}

