interface DefaultRoleCountPickerProps {
  count: number;
  saving: boolean;
  onChange: (count: number) => void;
}

export function DefaultRoleCountPicker({
  count,
  saving,
  onChange,
}: DefaultRoleCountPickerProps) {
  return (
    <section className="settings-card">
      <div className="settings-card-heading">
        <p className="eyebrow">Defaults</p>
        <h2>Default number of roles</h2>
      </div>
      <p className="settings-card-copy">
        Used by the role planner and as the number of saved roles selected for a library panel.
      </p>
      <div className="role-count-picker" role="radiogroup" aria-label="Default role count">
        {[3, 4, 5].map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={count === option}
            className={`role-count-option ${count === option ? "selected" : ""}`}
            disabled={saving}
            onClick={() => onChange(option)}
          >
            {option}
          </button>
        ))}
      </div>
    </section>
  );
}
