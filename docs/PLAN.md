# AI Swarm Analysis Framework Specification

## Summary

Create `outputs/ai-swarm-framework-spec.md`, a self-contained product requirements and technical design document that an AI coding agent can implement without additional decisions.

The specification will define a greenfield, local single-user web application using:

- Python 3.12, FastAPI, Pydantic v2, and `httpx`
- React, TypeScript, and Vite
- OpenAI-compatible `/v1/chat/completions` endpoints, including Ollama
- In-memory run history and asynchronous single-process execution
- Server-Sent Events for live stage updates
- A full results timeline and client-side Markdown export

Include a Mermaid diagram showing the complete orchestration and data flow.

## Product and UX Specification

- Define the user goal: submit an important decision and receive a multi-angle analysis whose disagreements remain visible.
- Specify the workflow:
  1. Enter a decision.
  2. Choose whether to include the debate round; enabled by default.
  3. Start the analysis.
  4. Watch role planning, independent experts, rebuttals, devil’s advocate, and synthesis appear live.
  5. Reopen runs from the current server session.
  6. Download the complete analysis as Markdown.
- Require a responsive single-page UI with a decision composer, session-history list, stage timeline, expert cards, debate responses, devil’s-advocate section, final verdict, and stage-specific error state.
- Render model-generated Markdown without enabling raw HTML.
- Define success through visible 3–5-role diversity, independent first-round analysis, conflict-preserving synthesis, live progress, session restoration, and valid Markdown export.
- Frame authentication, databases, distributed workers, billing, tool use, and public hosting as future extensions.

## Technical Design and Contracts

- Define the exact pipeline:
  - Orchestrator: one model call at temperature `0.9`, producing 3–5 validated `{name, focus, bias}` roles.
  - Experts: one parallel call per role at `0.7`; each receives the decision and its own role only.
  - Debate: optional parallel rebuttal calls at `0.6`; each receives its original opinion and all opposing opinions.
  - Devil’s advocate: one call at `0.8` after the active expert round, attacking shared assumptions.
  - Merge: one call at `0.4`, receiving the active expert opinions and devil’s-advocate response.
  - Total calls: `N + 3` without debate and `2N + 3` with debate.
- Include original prompt templates that preserve the article’s intent while avoiding copied prose.
- Define `LLMClient.complete(system, user, temperature) -> str` as an injectable asynchronous provider interface.
- Configure the server through:
  - `LLM_BASE_URL=http://localhost:11434/v1`
  - `LLM_API_KEY=ollama`
  - `LLM_MODEL=qwen2.5:32b`
  - `LLM_TIMEOUT_SECONDS=120`
  - Five stage-specific temperature variables
  - `CORS_ORIGINS=http://localhost:5173`
- Specify strict role-array extraction, JSON parsing, Pydantic validation, provider timeout behavior, and terminal run failures that preserve completed stage outputs.
- Define process-memory storage using UUIDv4 run IDs, UTC ISO-8601 timestamps, buffered events, and background `asyncio.Task` execution.

### Public HTTP interfaces

- `POST /api/runs`
  - Input: `{ "decision": string, "debate": boolean = true }`
  - Validation: trimmed decision length from 1 to 20,000 characters
  - Output: HTTP `202` with a run summary
- `GET /api/runs?limit=20`
  - Returns newest-first session history
- `GET /api/runs/{run_id}`
  - Returns the current run snapshot or `404`
- `GET /api/runs/{run_id}/events`
  - Returns `text/event-stream`
  - Supports `Last-Event-ID` and buffered-event replay

Define shared types for `RoleSpec`, `ExpertOpinion`, `RunStatus`, `RunStage`, `RunSummary`, `RunRecord`, and `RunEvent`. Use snake_case JSON fields, UUID strings, and UTC timestamps.

Define SSE event names:

- `run.created`
- `stage.started`
- `roles.planned`
- `expert.completed`
- `debate.completed`
- `advocate.completed`
- `synthesis.completed`
- `run.completed`
- `run.failed`
- `heartbeat`

Each event will have a monotonic numeric ID and a JSON envelope containing `run_id`, `type`, `timestamp`, and `data`.

The downloaded file will be named `swarm-analysis-YYYY-MM-DD-<short-id>.md` and contain the decision, metadata, roles, initial opinions, optional rebuttals, devil’s-advocate analysis, and final synthesis.

## Validation and Acceptance Tests

- Unit-test role extraction, validation, prompt composition, status transitions, and Markdown serialization.
- Prove first-round independence by asserting that expert requests contain no peer outputs.
- Verify parallel expert and debate execution with a barrier-controlled fake provider.
- Verify call counts and ordering for debate-enabled and debate-disabled runs.
- Verify that the devil’s advocate receives the active expert round and the merge receives the advocate response.
- Test provider errors, timeouts, malformed role JSON, missing runs, invalid decisions, and terminal SSE failure events.
- Test SSE ordering, heartbeat behavior, buffered replay, reconnect through `Last-Event-ID`, and completed-run replay.
- Test React stage rendering, session restoration, disabled submission states, error presentation, and Markdown download content.
- Add an end-to-end test using an injected fake provider and a manual Ollama smoke-test procedure.
- Require backend tests, frontend tests, type checks, linting, and production builds to pass.

## Assumptions and References

- The target is a trusted local machine or LAN.
- Runs remain available until the backend process restarts.
- Progress events represent completed orchestration stages rather than token-level generation.
- One failed required model call fails the run while retaining previously completed outputs.
- The backend owns endpoint, model, key, timeout, and temperature configuration.

Reference the following sources by name and full link inside the document:

- h100envy, “A Swarm of Agents for Multi-Angle Analysis” ([https://x.com/h100envy/status/2077371640690672001](https://x.com/h100envy/status/2077371640690672001))
- Ollama, “OpenAI compatibility” ([https://docs.ollama.com/api/openai-compatibility](https://docs.ollama.com/api/openai-compatibility))
- FastAPI, “Custom Responses and StreamingResponse” ([https://fastapi.tiangolo.com/advanced/custom-response/](https://fastapi.tiangolo.com/advanced/custom-response/))
- MDN Web Docs, “Using server-sent events” ([https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events))
- Vite, “Getting Started” ([https://vite.dev/guide/](https://vite.dev/guide/))
