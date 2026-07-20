import { useState } from "react";
import { submitClarification } from "../api";

type ClarificationFormProps = {
  runId: string;
  questions: string[];
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Could not submit clarification.";
}

export function ClarificationForm({ runId, questions }: ClarificationFormProps) {
  const [answers, setAnswers] = useState(() => questions.map(() => ""));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(skipped: boolean) {
    setSubmitting(true);
    setError(null);
    try {
      await submitClarification(runId, { answers: skipped ? [] : answers, skipped });
    } catch (nextError) {
      setError(errorMessage(nextError));
      setSubmitting(false);
    }
  }

  const incomplete = answers.some((answer) => !answer.trim());
  return (
    <div className="clarification-form">
      <p className="eyebrow">Before we design the panel</p>
      <h3>A little more context will sharpen the lenses.</h3>
      <div className="clarification-questions">
        {questions.map((question, index) => (
          <label key={question}>
            <span>{question}</span>
            <textarea
              value={answers[index]}
              onChange={(event) => {
                const next = [...answers];
                next[index] = event.target.value;
                setAnswers(next);
              }}
              rows={3}
              disabled={submitting}
            />
          </label>
        ))}
      </div>
      <div className="clarification-actions">
        <button type="button" className="secondary-button" disabled={submitting} onClick={() => void submit(true)}>
          Skip questions
        </button>
        <button
          type="button"
          className="primary-button"
          disabled={submitting || incomplete}
          onClick={() => void submit(false)}
        >
          {submitting ? "Continuing…" : "Continue to role planning"}
          <span aria-hidden="true">→</span>
        </button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}
