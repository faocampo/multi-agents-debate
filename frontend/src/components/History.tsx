import type { RunSummary } from "../types";

interface HistoryProps {
  runs: RunSummary[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (runId: string) => void;
  onRetry: () => void;
}

function timeLabel(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function History({
  runs,
  selectedId,
  loading,
  error,
  onSelect,
  onRetry,
}: HistoryProps) {
  return (
    <aside className="history-panel" aria-label="Session history">
      <div className="history-heading">
        <div>
          <p className="eyebrow">This session</p>
          <h2>Analysis history</h2>
        </div>
        <span className="history-count">{runs.length}</span>
      </div>
      {loading && <p className="pending-copy">Loading session…</p>}
      {error && (
        <div className="inline-error">
          <p>{error}</p>
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
      {!loading && !error && runs.length === 0 && (
        <div className="history-empty">
          <span aria-hidden="true">◎</span>
          <p>Your analyses will stay here until the server restarts.</p>
        </div>
      )}
      <div className="history-list">
        {runs.map((run) => (
          <button
            type="button"
            className={`history-item ${selectedId === run.id ? "selected" : ""}`}
            key={run.id}
            onClick={() => onSelect(run.id)}
            aria-pressed={selectedId === run.id}
          >
            <span className="history-status-row">
              <span className={`status-dot ${run.status}`} />
              <span>{run.status === "running" ? run.stage.replaceAll("_", " ") : run.status}</span>
              <time dateTime={run.created_at}>{timeLabel(run.created_at)}</time>
            </span>
            <strong>{run.decision_excerpt}</strong>
            <span className="history-meta">
              {run.role_count || "—"} lenses · {run.debate ? "debate on" : "direct synthesis"}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

