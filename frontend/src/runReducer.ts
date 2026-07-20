import type {
  ExpertOpinion,
  RoleSpec,
  RunError,
  RunEvent,
  RunRecord,
  RunStage,
  RunSummary,
} from "./types";

function orderOpinions(roles: RoleSpec[], opinions: ExpertOpinion[]): ExpertOpinion[] {
  const byName = new Map(opinions.map((opinion) => [opinion.role.name, opinion]));
  return roles.flatMap((role) => {
    const opinion = byName.get(role.name);
    return opinion ? [opinion] : [];
  });
}

export function applyRunEvent(run: RunRecord, event: RunEvent): RunRecord {
  switch (event.type) {
    case "stage.started":
      return {
        ...run,
        status: "running",
        stage: (event.data as { stage: RunStage }).stage,
        started_at: run.started_at ?? event.timestamp,
      };
    case "clarification.requested":
      return {
        ...run,
        stage: "awaiting_clarification",
        clarifying_questions: (event.data as { questions: string[] }).questions,
      };
    case "clarification.answered": {
      const data = event.data as { answers: string[]; skipped: boolean };
      return {
        ...run,
        clarifying_answers: data.answers,
        clarification_skipped: data.skipped,
      };
    }
    case "roles.planned": {
      const roles = (event.data as { roles: RoleSpec[] }).roles;
      return { ...run, roles, expert_opinions: orderOpinions(roles, run.expert_opinions) };
    }
    case "expert.completed": {
      const next = (event.data as { opinion: ExpertOpinion }).opinion;
      const opinions = run.expert_opinions.filter(
        (opinion) => opinion.role.name !== next.role.name,
      );
      opinions.push(next);
      return { ...run, expert_opinions: orderOpinions(run.roles, opinions) };
    }
    case "debate.completed": {
      const data = event.data as {
        role_name: string;
        rebuttal: string;
        completed_at: string;
      };
      return {
        ...run,
        expert_opinions: run.expert_opinions.map((opinion) =>
          opinion.role.name === data.role_name
            ? {
                ...opinion,
                rebuttal: data.rebuttal,
                rebuttal_completed_at: data.completed_at,
              }
            : opinion,
        ),
      };
    }
    case "advocate.completed":
      return { ...run, advocate_analysis: (event.data as { analysis: string }).analysis };
    case "synthesis.completed":
      return { ...run, synthesis: (event.data as { synthesis: string }).synthesis };
    case "run.completed": {
      const summary = (event.data as { summary: RunSummary }).summary;
      return {
        ...run,
        status: "completed",
        stage: "completed",
        completed_at: summary.completed_at,
      };
    }
    case "run.failed": {
      const data = event.data as { error: RunError; summary: RunSummary };
      return {
        ...run,
        status: "failed",
        stage: "failed",
        completed_at: data.summary.completed_at,
        error: data.error,
      };
    }
    default:
      return run;
  }
}

export function isTerminal(run: Pick<RunRecord, "status">): boolean {
  return run.status === "completed" || run.status === "failed";
}

