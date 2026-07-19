import { useState } from "react";
import type { RoleDefinition, RoleInput } from "../types";
import { DefaultRoleCountPicker } from "./settings/DefaultRoleCountPicker";
import { RoleForm } from "./settings/RoleForm";
import { RoleList } from "./settings/RoleList";
import { useRoleLibrary } from "./settings/useRoleLibrary";

interface SettingsProps {
  onBack: () => void;
}

export function Settings({ onBack }: SettingsProps) {
  const library = useRoleLibrary();
  const [editing, setEditing] = useState<RoleDefinition | null>(null);

  async function save(input: RoleInput, roleId?: string): Promise<boolean> {
    const saved = await library.saveRole(input, roleId);
    if (!saved) return false;
    setEditing(null);
    return true;
  }

  async function remove(role: RoleDefinition): Promise<void> {
    const removed = await library.removeRole(role);
    if (removed && editing?.id === role.id) setEditing(null);
  }

  return (
    <section className="settings-view">
      <div className="settings-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Agent roles library</h1>
          <p className="settings-lede">
            Save reusable expert lenses. Use a complete saved panel or let the model plan fresh roles.
          </p>
        </div>
        <button type="button" className="secondary-button" onClick={onBack}>
          Back to analysis <span aria-hidden="true">→</span>
        </button>
      </div>

      {library.loadError && (
        <div className="inline-error settings-load-error" role="alert">
          <p>{library.loadError}</p>
          <button type="button" onClick={() => void library.refresh()}>Retry</button>
        </div>
      )}

      {library.loading && !library.loadError && (
        <div className="loading-panel"><span /> Loading settings…</div>
      )}

      {!library.loading && !library.loadError && library.settings && (
        <>
          <DefaultRoleCountPicker
            count={library.settings.default_role_count}
            saving={library.countSaving}
            onChange={(count) => void library.changeCount(count)}
          />
          <RoleForm
            key={editing?.id ?? "new"}
            editing={editing}
            saving={library.saving}
            error={library.operationError}
            onSave={save}
            onCancel={() => {
              setEditing(null);
              library.clearOperationError();
            }}
          />
          <RoleList
            roles={library.settings.roles}
            editingId={editing?.id ?? null}
            saving={library.saving}
            onEdit={(role) => {
              setEditing(role);
              library.clearOperationError();
            }}
            onDelete={remove}
          />
        </>
      )}
    </section>
  );
}
