import { useState } from "react";
import type { FormEvent } from "react";
import type { RoleDefinition, RoleInput } from "../../types";

interface RoleFormProps {
  editing: RoleDefinition | null;
  saving: boolean;
  error: string | null;
  onSave: (input: RoleInput, roleId?: string) => Promise<boolean>;
  onCancel: () => void;
}

const EMPTY_DRAFT: RoleInput = { name: "", focus: "", bias: "", prompt: null };
const LIMITS = { name: 80, focus: 500, bias: 300, prompt: 2000 };

function normalize(draft: RoleInput): RoleInput {
  return {
    name: draft.name.trim(),
    focus: draft.focus.trim(),
    bias: draft.bias.trim(),
    prompt: draft.prompt?.trim() || null,
  };
}

function isValid(draft: RoleInput): boolean {
  const value = normalize(draft);
  return Boolean(
    value.name &&
      value.name.length <= LIMITS.name &&
      value.focus &&
      value.focus.length <= LIMITS.focus &&
      value.bias &&
      value.bias.length <= LIMITS.bias &&
      (!value.prompt || value.prompt.length <= LIMITS.prompt),
  );
}

export function RoleForm({ editing, saving, error, onSave, onCancel }: RoleFormProps) {
  const [draft, setDraft] = useState<RoleInput>(() =>
    editing
      ? {
          name: editing.name,
          focus: editing.focus,
          bias: editing.bias,
          prompt: editing.prompt,
        }
      : EMPTY_DRAFT,
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!isValid(draft) || saving) return;
    const saved = await onSave(normalize(draft), editing?.id);
    if (saved) setDraft(EMPTY_DRAFT);
  }

  return (
    <section className="settings-card">
      <div className="settings-card-heading">
        <p className="eyebrow">{editing ? "Edit role" : "New role"}</p>
        <h2>{editing ? "Update a saved lens" : "Add a role to the library"}</h2>
      </div>
      <form className="role-form" onSubmit={(event) => void submit(event)}>
        <RoleField
          label="Name"
          value={draft.name}
          maxLength={LIMITS.name}
          placeholder="Customer Advocate"
          onChange={(name) => setDraft((current) => ({ ...current, name }))}
          singleLine
        />
        <RoleField
          label="Focus"
          value={draft.focus}
          maxLength={LIMITS.focus}
          placeholder="What this lens is responsible for analyzing."
          onChange={(focus) => setDraft((current) => ({ ...current, focus }))}
        />
        <RoleField
          label="Bias"
          value={draft.bias}
          maxLength={LIMITS.bias}
          placeholder="The deliberate perspective or default concern."
          onChange={(bias) => setDraft((current) => ({ ...current, bias }))}
        />
        <RoleField
          label="Prompt (optional)"
          value={draft.prompt ?? ""}
          maxLength={LIMITS.prompt}
          placeholder="Free-form guidance forwarded to the expert alongside the role mandate."
          onChange={(prompt) => setDraft((current) => ({ ...current, prompt: prompt || null }))}
          prompt
        />
        <div className="role-form-actions">
          <button type="submit" className="primary-button" disabled={!isValid(draft) || saving}>
            {saving ? "Saving…" : editing ? "Save changes" : "Add role"}
            <span aria-hidden="true">→</span>
          </button>
          {editing && (
            <button type="button" className="secondary-button" onClick={onCancel}>
              Cancel
            </button>
          )}
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
      </form>
    </section>
  );
}

interface RoleFieldProps {
  label: string;
  value: string;
  maxLength: number;
  placeholder: string;
  onChange: (value: string) => void;
  singleLine?: boolean;
  prompt?: boolean;
}

function RoleField({
  label,
  value,
  maxLength,
  placeholder,
  onChange,
  singleLine = false,
  prompt = false,
}: RoleFieldProps) {
  return (
    <label className={`role-field ${prompt ? "role-field-prompt" : ""}`}>
      <span>{label}</span>
      {singleLine ? (
        <input
          type="text"
          value={value}
          maxLength={maxLength}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
        />
      ) : (
        <textarea
          value={value}
          maxLength={maxLength}
          rows={prompt ? 4 : 2}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
        />
      )}
      <small>{value.trim().length} / {maxLength}</small>
    </label>
  );
}
