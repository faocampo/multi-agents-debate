import { useCallback, useEffect, useRef, useState } from "react";
import {
  createRun,
  getRoleLibrarySettings,
  getRun,
  listRuns,
  runEventsUrl,
} from "./api";
import { Composer } from "./components/Composer";
import { History } from "./components/History";
import { RunView } from "./components/RunView";
import { Settings } from "./components/Settings";
import { applyRunEvent, isTerminal } from "./runReducer";
import type {
  RoleLibrarySettings,
  RoleSource,
  RunEvent,
  RunRecord,
  RunSummary,
} from "./types";

const eventNames: RunEvent["type"][] = [
  "run.created",
  "stage.started",
  "clarification.requested",
  "clarification.answered",
  "roles.planned",
  "expert.completed",
  "debate.completed",
  "advocate.completed",
  "synthesis.completed",
  "run.completed",
  "run.failed",
  "heartbeat",
];

type ConnectionState = "closed" | "connecting" | "live" | "reconnecting" | "disconnected";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export default function App() {
  const [view, setView] = useState<"analysis" | "settings">("analysis");
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunRecord | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [decision, setDecision] = useState("");
  const [debate, setDebate] = useState(true);
  const [clarify, setClarify] = useState(false);
  const [roleLibrary, setRoleLibrary] = useState<RoleLibrarySettings | null>(null);
  const [roleLibraryError, setRoleLibraryError] = useState<string | null>(null);
  const [useSavedRoles, setUseSavedRoles] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("closed");
  const sourceRef = useRef<EventSource | null>(null);
  const selectedIdRef = useRef<string | null>(null);
  const appliedEventsRef = useRef(new Set<number>());

  const refreshRoleLibrary = useCallback(async () => {
    setRoleLibraryError(null);
    try {
      setRoleLibrary(await getRoleLibrarySettings());
    } catch (error) {
      setRoleLibraryError(errorMessage(error));
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const settings = await getRoleLibrarySettings();
        if (active) setRoleLibrary(settings);
      } catch (error) {
        if (active) setRoleLibraryError(errorMessage(error));
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      setHistory(await listRuns());
    } catch (error) {
      setHistoryError(errorMessage(error));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const selectRun = useCallback(async (runId: string) => {
    sourceRef.current?.close();
    selectedIdRef.current = runId;
    setSelectedId(runId);
    setSelectedRun(null);
    setConnection("closed");
    setRunLoading(true);
    setRunError(null);
    appliedEventsRef.current = new Set();
    try {
      const run = await getRun(runId);
      if (selectedIdRef.current === runId) {
        setConnection(isTerminal(run) ? "closed" : "connecting");
        setSelectedRun(run);
      }
    } catch (error) {
      if (selectedIdRef.current === runId) setRunError(errorMessage(error));
    } finally {
      if (selectedIdRef.current === runId) setRunLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const runs = await listRuns();
        if (!active) return;
        setHistory(runs);
        if (runs[0]) await selectRun(runs[0].id);
      } catch (error) {
        if (active) setHistoryError(errorMessage(error));
      } finally {
        if (active) setHistoryLoading(false);
      }
    }
    void initialize();
    return () => {
      active = false;
      sourceRef.current?.close();
    };
  }, [selectRun]);

  const availableRoleCount = roleLibrary?.roles.length ?? 0;
  const defaultRoleCount = roleLibrary?.default_role_count ?? 3;
  const canUseSavedRoles = availableRoleCount >= defaultRoleCount;
  const streamRunId = selectedRun && !isTerminal(selectedRun) ? selectedRun.id : null;

  useEffect(() => {
    if (!streamRunId) return;

    const source = new EventSource(runEventsUrl(streamRunId));
    sourceRef.current = source;

    source.onopen = () => setConnection("live");
    source.onerror = () => {
      setConnection(source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting");
    };

    function handle(message: MessageEvent<string>) {
      const event = JSON.parse(message.data) as RunEvent;
      if (event.run_id !== selectedIdRef.current || appliedEventsRef.current.has(event.id)) return;
      appliedEventsRef.current.add(event.id);
      setConnection("live");
      setSelectedRun((current) => (current ? applyRunEvent(current, event) : current));

      if (event.type === "stage.started") {
        const stage = (event.data as { stage: RunSummary["stage"] }).stage;
        setHistory((current) =>
          current.map((item) =>
            item.id === event.run_id ? { ...item, status: "running", stage } : item,
          ),
        );
      }
      if (event.type === "roles.planned") {
        const roleCount = (event.data as { roles: unknown[] }).roles.length;
        setHistory((current) =>
          current.map((item) => (item.id === event.run_id ? { ...item, role_count: roleCount } : item)),
        );
      }
      if (event.type === "run.completed" || event.type === "run.failed") {
        const summary = (event.data as { summary: RunSummary }).summary;
        setHistory((current) => current.map((item) => (item.id === summary.id ? summary : item)));
        source.close();
        setConnection("closed");
        void getRun(event.run_id).then((snapshot) => {
          if (selectedIdRef.current === event.run_id) setSelectedRun(snapshot);
        });
      }
    }

    eventNames.forEach((name) => source.addEventListener(name, handle as EventListener));
    return () => {
      eventNames.forEach((name) => source.removeEventListener(name, handle as EventListener));
      source.close();
    };
  }, [streamRunId]);

  function openAnalysis() {
    setView("analysis");
    void refreshRoleLibrary();
    void refreshHistory();
  }

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const roleSource: RoleSource = useSavedRoles && canUseSavedRoles ? "library" : "planned";
      const summary = await createRun(decision.trim(), debate, roleSource, clarify && roleSource === "planned");
      setHistory((current) => [summary, ...current.filter((item) => item.id !== summary.id)].slice(0, 20));
      setDecision("");
      await selectRun(summary.id);
    } catch (error) {
      setSubmitError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="AI Swarm Analysis home">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <span>AI Swarm <strong>Analysis</strong></span>
        </a>
        <nav className="header-nav">
          <button
            type="button"
            className={`header-link ${view === "analysis" ? "active" : ""}`}
            onClick={openAnalysis}
          >
            Analysis
          </button>
          <button
            type="button"
            className={`header-link ${view === "settings" ? "active" : ""}`}
            onClick={() => setView("settings")}
          >
            Settings
          </button>
          <div className="header-note"><span /> Local session · private by design</div>
        </nav>
      </header>

      <main id="top">
        {view === "settings" ? (
          <Settings onBack={openAnalysis} />
        ) : (
          <>
            <section className="hero">
              <p className="eyebrow">Many lenses. One consequential decision.</p>
              <h1>A verdict that keeps the <em>disagreement</em> that matters.</h1>
              <p>
                Independent experts analyze in parallel, challenge one another, and expose the costs
                hidden inside easy consensus.
              </p>
            </section>

            <Composer
              decision={decision}
              debate={debate}
              clarify={clarify}
              submitting={submitting}
              error={submitError}
              useSavedRoles={useSavedRoles}
              savedRoleCount={roleLibrary?.roles.length ?? 0}
              defaultRoleCount={roleLibrary?.default_role_count ?? 3}
              roleLibraryError={roleLibraryError}
              onDecisionChange={setDecision}
              onDebateChange={setDebate}
              onClarifyChange={setClarify}
              onUseSavedRolesChange={setUseSavedRoles}
              onOpenSettings={() => setView("settings")}
              onSubmit={submit}
            />

            <div className="workspace">
              <History
                runs={history}
                selectedId={selectedId}
                loading={historyLoading}
                error={historyError}
                onSelect={(runId) => void selectRun(runId)}
                onRetry={() => void refreshHistory()}
              />
              <section className="active-run" aria-live="polite">
                {runLoading && <div className="run-placeholder"><span /> Restoring analysis…</div>}
                {runError && (
                  <div className="inline-error run-load-error" role="alert">
                    <p>{runError}</p>
                    {selectedId && <button onClick={() => void selectRun(selectedId)}>Retry</button>}
                  </div>
                )}
                {!runLoading && !runError && !selectedRun && (
                  <div className="no-run-selected">
                    <span aria-hidden="true">✦</span>
                    <h2>Your panel is ready when you are.</h2>
                    <p>Describe a decision above to start an independent multi-angle analysis.</p>
                  </div>
                )}
                {selectedRun && <RunView run={selectedRun} connection={connection} />}
              </section>
            </div>
          </>
        )}
      </main>

      <footer>
        <span>AI Swarm Analysis</span>
        <p>Session data clears when the local server restarts.</p>
      </footer>
    </div>
  );
}
