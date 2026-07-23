import { useState, type FormEvent } from "react";
import type { RunRecord } from "../types";
import { downloadRunMarkdown } from "../exportMarkdown";
import { ClarificationForm } from "./ClarificationForm";
import { ExpertCard } from "./ExpertCard";
import { MarkdownSection } from "./MarkdownSection";
import { StageTimeline } from "./StageTimeline";

interface RunViewProps {
  run: RunRecord;
  connection: "closed" | "connecting" | "live" | "reconnecting" | "disconnected";
  challengeSubmitting: boolean;
  challengeError: string | null;
  onChallenge: (kind: "question" | "challenge", input: string) => void | Promise<void>;
}

function formatDate(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function ClarificationSummary({ run }: { run: RunRecord }) {
  if (run.clarifying_questions.length === 0) return null;
  if (run.clarifying_answers === null && !run.clarification_skipped) return null;

  return (
    <section className="results-section clarification-summary-section" id="clarification-summary">
      <details open>
        <summary>
          <span>
            <span className="eyebrow">Clarifying context</span>
            <strong>
              {run.clarification_skipped
                ? "Clarifying questions were skipped"
                : `${run.clarifying_questions.length} answered question${run.clarifying_questions.length === 1 ? "" : "s"}`}
            </strong>
          </span>
          <small>{run.clarification_skipped ? "No extra context added" : "View answers"}</small>
        </summary>
        {!run.clarification_skipped && (
          <dl className="clarification-summary-list">
            {run.clarifying_questions.map((question, index) => (
              <div key={question}>
                <dt>{question}</dt>
                <dd>{run.clarifying_answers?.[index] ?? "No answer recorded."}</dd>
              </div>
            ))}
          </dl>
        )}
      </details>
    </section>
  );
}

export function RunView({
  run,
  connection,
  challengeSubmitting,
  challengeError,
  onChallenge,
}: RunViewProps) {
  const live = run.status === "queued" || run.status === "running";
  const [challengeKind, setChallengeKind] = useState<"question" | "challenge">("challenge");
  const [challengeInput, setChallengeInput] = useState("");

  async function submitChallenge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = challengeInput.trim();
    if (!trimmed || challengeSubmitting) return;
    await onChallenge(challengeKind, trimmed);
    setChallengeInput("");
  }

  return (
    <article className="run-view">
      <header className="run-header">
        <div className="run-title-block">
          <div className="run-meta-row">
            <span className={`run-status ${run.status}`}>{run.status}</span>
            {run.challenge && <span>Challenge run</span>}
            <span>{run.debate ? "Debate enabled" : "Direct synthesis"}</span>
            <time dateTime={run.created_at}>{formatDate(run.created_at)}</time>
            {live && <span className={`connection ${connection}`}>{connection}</span>}
          </div>
          <p className="eyebrow">Decision under analysis</p>
          <h2>{run.decision}</h2>
          {run.challenge && (
            <p className="challenge-summary">
              {run.challenge.kind === "question" ? "Question" : "Challenge"}: {run.challenge.input}
            </p>
          )}
        </div>
        <button className="secondary-button" type="button" onClick={() => downloadRunMarkdown(run)}>
          Download .md <span aria-hidden="true">↓</span>
        </button>
      </header>

      <StageTimeline run={run} />

      {run.challenge && (
        <section className="results-section challenge-context">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Reopened conclusion</p>
              <h2>Parent conclusion under review</h2>
            </div>
            <p>Run lineage: {run.root_run_id?.slice(0, 8)} -&gt; {run.parent_run_id?.slice(0, 8)}</p>
          </div>
          <MarkdownSection content={run.challenge.parent_conclusion} />
        </section>
      )}

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

      {run.clarifying_questions.length > 0 &&
        run.clarifying_answers === null &&
        !run.clarification_skipped && (
          <section className="results-section clarification-section" id="clarification">
            <ClarificationForm runId={run.id} questions={run.clarifying_questions} />
          </section>
        )}
      <ClarificationSummary run={run} />

      <section className="results-section roles-section" id="panel">
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
                challenge={run.challenge !== null}
                index={index}
              />
            ))}
          </div>
        )}
      </section>

      <section className="results-section advocate-section" id="advocate">
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

      <section className="results-section synthesis-section" id="synthesis">
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

      {run.status === "completed" && run.synthesis && (
        <section className="results-section challenge-section" id="challenge">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Reopen the debate</p>
              <h2>Challenge this conclusion</h2>
            </div>
            <p>The same role panel will reconsider the conclusion and produce a new child run.</p>
          </div>
          <form className="challenge-form" onSubmit={submitChallenge}>
            <div className="segmented-control" aria-label="Challenge type">
              <button
                type="button"
                className={challengeKind === "challenge" ? "active" : ""}
                onClick={() => setChallengeKind("challenge")}
              >
                Challenge
              </button>
              <button
                type="button"
                className={challengeKind === "question" ? "active" : ""}
                onClick={() => setChallengeKind("question")}
              >
                Question
              </button>
            </div>
            <label>
              <span>{challengeKind === "question" ? "Question" : "Challenge"}</span>
              <textarea
                value={challengeInput}
                onChange={(event) => setChallengeInput(event.target.value)}
                maxLength={5000}
                rows={4}
                placeholder="What should the panel reconsider?"
              />
            </label>
            {challengeError && <p className="inline-error" role="alert">{challengeError}</p>}
            <button
              className="primary-button"
              type="submit"
              disabled={!challengeInput.trim() || challengeSubmitting}
            >
              {challengeSubmitting ? "Reopening…" : "Recreate debate"}
            </button>
          </form>
        </section>
      )}
    </article>
  );
}
