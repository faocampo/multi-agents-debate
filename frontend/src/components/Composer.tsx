import type { FormEvent } from "react";

interface ComposerProps {
  decision: string;
  debate: boolean;
  clarify: boolean;
  submitting: boolean;
  error: string | null;
  useSavedRoles: boolean;
  savedRoleCount: number;
  defaultRoleCount: number;
  roleLibraryError: string | null;
  onDecisionChange: (value: string) => void;
  onDebateChange: (value: boolean) => void;
  onClarifyChange: (value: boolean) => void;
  onUseSavedRolesChange: (value: boolean) => void;
  onOpenSettings: () => void;
  onSubmit: () => void;
}

export function Composer({
  decision,
  debate,
  clarify,
  submitting,
  error,
  useSavedRoles,
  savedRoleCount,
  defaultRoleCount,
  roleLibraryError,
  onDecisionChange,
  onDebateChange,
  onClarifyChange,
  onUseSavedRolesChange,
  onOpenSettings,
  onSubmit,
}: ComposerProps) {
  const trimmedLength = decision.trim().length;
  const invalid = trimmedLength === 0 || trimmedLength > 20_000;
  const canUseSavedRoles = !roleLibraryError && savedRoleCount >= defaultRoleCount;
  const missingRoleCount = Math.max(0, defaultRoleCount - savedRoleCount);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!invalid && !submitting) onSubmit();
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-heading">
        <div>
          <p className="eyebrow">New analysis</p>
          <h2>What decision deserves more than one answer?</h2>
        </div>
        <span className={`character-count ${trimmedLength > 20_000 ? "over" : ""}`}>
          {decision.length.toLocaleString()} / 20,000
        </span>
      </div>
      <label className="sr-only" htmlFor="decision">
        Decision to analyze
      </label>
      <textarea
        id="decision"
        value={decision}
        onChange={(event) => onDecisionChange(event.target.value)}
        placeholder="Should we change our pricing model next quarter? Include context, constraints, and the stakes."
        rows={5}
        aria-invalid={trimmedLength > 20_000}
        aria-describedby={error ? "composer-error" : undefined}
      />
      <div className="composer-actions">
        <div className="composer-toggles">
          <label className="debate-toggle">
            <input
              type="checkbox"
              checked={debate}
              onChange={(event) => onDebateChange(event.target.checked)}
            />
            <span className="toggle-track" aria-hidden="true">
              <span />
            </span>
            <span>
              <strong>Include expert debate</strong>
              <small>Each lens responds to the others before synthesis.</small>
            </span>
          </label>
          <label className={`debate-toggle ${useSavedRoles ? "disabled" : ""}`}>
            <input
              type="checkbox"
              checked={clarify && !useSavedRoles}
              disabled={useSavedRoles}
              onChange={(event) => onClarifyChange(event.target.checked)}
            />
            <span className="toggle-track" aria-hidden="true">
              <span />
            </span>
            <span>
              <strong>Ask clarifying questions first</strong>
              <small>
                {useSavedRoles
                  ? "Available when planning a new panel."
                  : "Answer a few questions before lenses are designed."}
              </small>
            </span>
          </label>
          <label className={`debate-toggle ${canUseSavedRoles ? "" : "disabled"}`}>
            <input
              type="checkbox"
              checked={useSavedRoles && canUseSavedRoles}
              disabled={!canUseSavedRoles}
              onChange={(event) => {
                const checked = event.target.checked;
                onUseSavedRolesChange(checked);
                if (checked) onClarifyChange(false);
              }}
            />
            <span className="toggle-track" aria-hidden="true">
              <span />
            </span>
            <span>
              <strong>Use saved roles</strong>
              <small>
                {canUseSavedRoles
                  ? `Use the first ${defaultRoleCount} of ${savedRoleCount} saved lenses.`
                  : roleLibraryError
                    ? "Saved roles are temporarily unavailable."
                    : `Add ${missingRoleCount} more saved role${missingRoleCount === 1 ? "" : "s"} to use a complete panel.`}
              </small>
            </span>
          </label>
        </div>
        <div className="composer-submit-column">
          {!canUseSavedRoles && (
            <button
              type="button"
              className="composer-settings-link"
              onClick={onOpenSettings}
            >
              Open Settings
            </button>
          )}
          <button className="primary-button" type="submit" disabled={invalid || submitting}>
            {submitting ? "Starting analysis…" : "Analyze decision"}
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>
      {error && (
        <p className="form-error" id="composer-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

