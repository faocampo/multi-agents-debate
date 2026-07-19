import type { RunRecord, RunStage } from "../types";

const stages: Array<{ id: RunStage; label: string; short: string }> = [
  { id: "planning_roles", label: "Role planning", short: "Plan" },
  { id: "independent_analysis", label: "Independent experts", short: "Analyze" },
  { id: "debate", label: "Expert debate", short: "Debate" },
  { id: "devils_advocate", label: "Devil's advocate", short: "Stress-test" },
  { id: "synthesis", label: "Final synthesis", short: "Synthesize" },
];

type StageState = "pending" | "active" | "completed" | "skipped" | "failed";

function stateFor(run: RunRecord, stage: RunStage): StageState {
  if (stage === "debate" && !run.debate) return "skipped";
  if (run.error?.stage === stage) return "failed";
  if (stage === "planning_roles" && run.roles.length > 0) return "completed";
  if (
    stage === "independent_analysis" &&
    run.roles.length > 0 &&
    run.expert_opinions.length === run.roles.length
  )
    return "completed";
  if (
    stage === "debate" &&
    run.debate &&
    run.roles.length > 0 &&
    run.expert_opinions.every((opinion) => opinion.rebuttal)
  )
    return "completed";
  if (stage === "devils_advocate" && run.advocate_analysis) return "completed";
  if (stage === "synthesis" && run.synthesis) return "completed";
  if (run.stage === stage) return "active";
  return "pending";
}

export function StageTimeline({ run }: { run: RunRecord }) {
  return (
    <ol className="stage-timeline" aria-label="Analysis progress">
      {stages.map((stage, index) => {
        const state = stateFor(run, stage.id);
        return (
          <li className={state} key={stage.id}>
            <span className="stage-marker" aria-hidden="true">
              {state === "completed" ? "✓" : state === "failed" ? "!" : index + 1}
            </span>
            <span>
              <small>{stage.short}</small>
              <strong>{stage.label}</strong>
              <em>{state}</em>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

