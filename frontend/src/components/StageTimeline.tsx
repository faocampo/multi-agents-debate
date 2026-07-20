import type { RunRecord, RunStage } from "../types";

const stages: Array<{ id: RunStage; label: string; short: string; anchor: string | null }> = [
  { id: "awaiting_clarification", label: "Clarifying questions", short: "Clarify", anchor: "clarification" },
  { id: "planning_roles", label: "Role planning", short: "Plan", anchor: "panel" },
  { id: "independent_analysis", label: "Independent experts", short: "Analyze", anchor: "panel" },
  { id: "debate", label: "Expert debate", short: "Debate", anchor: "panel" },
  { id: "devils_advocate", label: "Devil's advocate", short: "Stress-test", anchor: "advocate" },
  { id: "synthesis", label: "Final synthesis", short: "Synthesize", anchor: "synthesis" },
];

type StageState = "pending" | "active" | "completed" | "skipped" | "failed";

function stateFor(run: RunRecord, stage: RunStage): StageState {
  if (stage === "awaiting_clarification" && !run.clarify) return "skipped";
  if (
    stage === "awaiting_clarification" &&
    (run.clarifying_answers !== null || run.clarification_skipped)
  )
    return "completed";
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

function scrollToSection(anchor: string) {
  document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function StageTimeline({ run }: { run: RunRecord }) {
  const visibleStages = run.clarify ? stages : stages.slice(1);
  return (
    <ol className={`stage-timeline ${run.clarify ? "has-clarification" : ""}`} aria-label="Analysis progress">
      {visibleStages.map((stage, index) => {
        const state = stateFor(run, stage.id);
        const clickable = stage.anchor !== null && state !== "pending";
        return (
          <li
            className={`${state} ${clickable ? "clickable" : ""}`}
            key={stage.id}
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
            aria-label={clickable ? `Jump to ${stage.label}` : undefined}
            onClick={clickable ? () => scrollToSection(stage.anchor!) : undefined}
            onKeyDown={
              clickable
                ? (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      scrollToSection(stage.anchor!);
                    }
                  }
                : undefined
            }
          >
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
