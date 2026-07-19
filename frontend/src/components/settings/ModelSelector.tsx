import { useEffect, useState } from "react";
import { listModels } from "../../api";
import type { LLMModelInfo } from "../../types";

interface ModelSelectorProps {
  selected: string | null;
  saving: boolean;
  error: string | null;
  onChange: (modelId: string) => void;
}

export function ModelSelector({ selected, saving, error, onChange }: ModelSelectorProps) {
  const [models, setModels] = useState<LLMModelInfo[]>([]);
  const [zdrOnly, setZdrOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function fetchModels() {
      setModelsError(null);
      try {
        const next = await listModels(zdrOnly);
        if (active) setModels(next);
      } catch (err) {
        if (active) {
          setModelsError(err instanceof Error ? err.message : "Could not load models");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void fetchModels();
    return () => {
      active = false;
    };
  }, [zdrOnly]);

  function toggleZdr(checked: boolean) {
    setLoading(true);
    setZdrOnly(checked);
  }

  const selectedInList = selected && models.some((model) => model.id === selected);
  const options = selected && !selectedInList
    ? [{ id: selected, name: `Current: ${selected}` }, ...models]
    : models;

  return (
    <div className="model-selector">
      <label className="role-field model-field">
        <span>Model</span>
        <select
          className="model-select"
          value={selected ?? ""}
          disabled={loading || saving}
          onChange={(event) => onChange(event.target.value)}
        >
          {loading ? (
            <option value="">Loading models…</option>
          ) : options.length === 0 ? (
            <option value="">No models available</option>
          ) : (
            <>
              <option value="" disabled>Choose a model…</option>
              {options.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </>
          )}
        </select>
      </label>
      <label className={`debate-toggle model-toggle ${loading || saving ? "disabled" : ""}`}>
        <input
          type="checkbox"
          checked={zdrOnly}
          disabled={loading || saving}
          onChange={(event) => toggleZdr(event.target.checked)}
        />
        <span className="toggle-track" aria-hidden="true"><span /></span>
        <span>
          <strong>Only show ZDR models</strong>
          <small>Filter to Zero Data Retention endpoints on OpenRouter.</small>
        </span>
      </label>
      {modelsError && <p className="form-error">{modelsError}</p>}
      {error && <p className="form-error">{error}</p>}
    </div>
  );
}
