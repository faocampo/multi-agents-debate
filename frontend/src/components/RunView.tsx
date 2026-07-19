import type { RunRecord } from "../types";
import { downloadRunMarkdown } from "../exportMarkdown";
import { ExpertCard } from "./ExpertCard";
import { MarkdownSection } from "./MarkdownSection";
import { StageTimeline } from "./StageTimeline";

interface RunViewProps {
  run: RunRecord;
  connection: "closed" | "connecting" | "live" | "reconnecting" | "disconnected";
}

function formatDate(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export function RunView({ run, connection }: RunViewProps) {
  const live = run.status === "queued" || run.status === "running";
  return (
    <article className="run-view">
      <header className="run-header">
        <div className="run-title-block">
          <div className="run-meta-row">
            <span className={`run-status ${run.status}`}>{run.status}</span>
            <span>{run.debate ? "Debate enabled" : "Direct synthesis"}</span>
            <time dateTime={run.created_at}>{formatDate(run.created_at)}</time>
            {live && <span className={`connection ${connection}`}>{connection}</span>}
          </div>
          <p className="eyebrow">Decision under analysis</p>
          <h2>{run.decision}</h2>
        </div>
        <button className="secondary-button" type="button" onClick={() => downloadRunMarkdown(run)}>
          Download .md <span aria-hidden="true">↓</span>
        </button>
      </header>

      <StageTimeline run={run} />

      {run.error && (
        <section className="run-error" role="alert">
          <span aria-hidden="true">!</span>
          <div>
            <p className="eyebrow">{run.error.stage.replaceAll("_", " ")} failed</p>
            <h3>This analysis stopped at one stage.</h3>
            <p>{run.error.message}</p>
            <small>Everything completed before the failure remains below and in the export.</small>
          </div>
        </section>
      )}

      <section className="results-section roles-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">The panel</p>
            <h2>{run.roles.length > 0 ? `${run.roles.length} independent lenses` : "Planning expert lenses"}</h2>
          </div>
          <p>Each first-round analysis receives only its own mandate.</p>
        </div>
        {run.roles.length === 0 ? (
          <div className="loading-panel"><span /> Designing a panel around your decision…</div>
        ) : (
          <div className="expert-grid">
            {run.roles.map((role, index) => (
              <ExpertCard
                key={role.name}
                role={role}
                opinion={run.expert_opinions.find((item) => item.role.name === role.name)}
                debate={run.debate}
                index={index}
              />
            ))}
          </div>
        )}
      </section>

      <section className="results-section advocate-section">
        <div className="section-label">
          <span>DA</span>
          <div>
            <p className="eyebrow">Stress test</p>
            <h2>Devil's advocate</h2>
          </div>
        </div>
        <MarkdownSection
          content={run.advocate_analysis}
          pendingLabel="Waiting for the active expert round…"
        />
      </section>

      <section className="results-section synthesis-section">
        <div className="synthesis-accent" aria-hidden="true">Verdict</div>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Conflict-preserving synthesis</p>
            <h2>The final verdict</h2>
          </div>
          <p>Agreement, clashes, costs, and conditions stay visible.</p>
        </div>
        <MarkdownSection content={run.synthesis} pendingLabel="The panel has not reached synthesis yet…" />
      </section>
    </article>
  );
}

