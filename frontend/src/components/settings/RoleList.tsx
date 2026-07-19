import { useState } from "react";
import type { RoleDefinition } from "../../types";

interface RoleListProps {
  roles: RoleDefinition[];
  editingId: string | null;
  saving: boolean;
  onEdit: (role: RoleDefinition) => void;
  onDelete: (role: RoleDefinition) => Promise<void>;
}

export function RoleList({ roles, editingId, saving, onEdit, onDelete }: RoleListProps) {
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  return (
    <section className="settings-card">
      <div className="settings-card-heading">
        <p className="eyebrow">Library</p>
        <h2>
          {roles.length === 0
            ? "No saved roles yet"
            : `${roles.length} saved role${roles.length === 1 ? "" : "s"}`}
        </h2>
      </div>
      {roles.length === 0 ? (
        <p className="settings-empty">
          Add your first role above. Saved roles appear here and can be used for a debate panel.
        </p>
      ) : (
        <ul className="role-list">
          {roles.map((role) => {
            const confirming = pendingDeleteId === role.id;
            return (
              <li
                key={role.id}
                className={`role-item ${editingId === role.id ? "editing" : ""}`}
              >
                <div className="role-item-header">
                  <strong>{role.name}</strong>
                  <span className="role-item-actions">
                    {confirming ? (
                      <>
                        <button
                          type="button"
                          className="secondary-button danger"
                          disabled={saving}
                          onClick={() => {
                            void onDelete(role).then(() => setPendingDeleteId(null));
                          }}
                        >
                          Confirm delete
                        </button>
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={saving}
                          onClick={() => setPendingDeleteId(null)}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => onEdit(role)}
                          disabled={saving}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="secondary-button danger"
                          onClick={() => setPendingDeleteId(role.id)}
                          disabled={saving}
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </span>
                </div>
                <p className="role-item-focus">{role.focus}</p>
                <p className="role-item-bias"><span>Bias</span> {role.bias}</p>
                {role.prompt && (
                  <p className="role-item-prompt"><span>Prompt</span> {role.prompt}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
