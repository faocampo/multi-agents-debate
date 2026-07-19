export type RunStatus = "queued" | "running" | "completed" | "failed";
export type RoleSource = "planned" | "library";

export type RunStage =
  | "queued"
  | "planning_roles"
  | "independent_analysis"
  | "debate"
  | "devils_advocate"
  | "synthesis"
  | "completed"
  | "failed";

export type RunEventType =
  | "run.created"
  | "stage.started"
  | "roles.planned"
  | "expert.completed"
  | "debate.completed"
  | "advocate.completed"
  | "synthesis.completed"
  | "run.completed"
  | "run.failed"
  | "heartbeat";

export interface RoleSpec {
  name: string;
  focus: string;
  bias: string;
  prompt?: string | null;
}

export interface RoleDefinition {
  id: string;
  name: string;
  focus: string;
  bias: string;
  prompt: string | null;
}

export interface LLMModelInfo {
  id: string;
  name: string;
  description?: string | null;
}

export interface RoleLibrarySettings {
  default_role_count: number;
  llm_model: string | null;
  roles: RoleDefinition[];
}

export interface RoleInput {
  name: string;
  focus: string;
  bias: string;
  prompt: string | null;
}

export interface ExpertOpinion {
  role: RoleSpec;
  initial_analysis: string;
  initial_completed_at: string;
  rebuttal: string | null;
  rebuttal_completed_at: string | null;
}

export interface RunError {
  stage: Exclude<RunStage, "queued" | "completed" | "failed">;
  code: string;
  message: string;
  retryable: boolean;
}

export interface RunSummary {
  id: string;
  decision_excerpt: string;
  debate: boolean;
  status: RunStatus;
  stage: RunStage;
  role_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface RunRecord {
  id: string;
  decision: string;
  debate: boolean;
  status: RunStatus;
  stage: RunStage;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  roles: RoleSpec[];
  expert_opinions: ExpertOpinion[];
  advocate_analysis: string | null;
  synthesis: string | null;
  error: RunError | null;
}

export interface RunEvent<T = Record<string, unknown>> {
  id: number;
  run_id: string;
  type: RunEventType;
  timestamp: string;
  data: T;
}

