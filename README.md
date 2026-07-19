# AI Swarm Analysis

A local decision-analysis application that assembles three to five independent expert lenses, optionally lets them debate, stress-tests their shared assumptions, and produces a conflict-preserving synthesis.

## Architecture

- `backend/`: Python 3.12, FastAPI, Pydantic v2, `httpx`, in-memory runs, and Server-Sent Events.
- `frontend/`: React, TypeScript, and Vite single-page interface.
- `e2e/`: deterministic fake OpenAI-compatible provider.
- `frontend/e2e/`: Playwright integration workflow.
- `outputs/ai-swarm-framework-spec.md`: complete product and technical specification.

The backend calls any OpenAI-compatible `/v1/chat/completions` endpoint. The default configuration targets Ollama, whose compatibility API is documented at Ollama, “OpenAI compatibility” ([https://docs.ollama.com/api/openai-compatibility](https://docs.ollama.com/api/openai-compatibility)).

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- A current Node.js LTS release and npm
- An OpenAI-compatible model provider; the defaults use [Ollama](https://ollama.com/)

## Local setup

```bash
cp .env.example .env

cd backend
uv sync --all-extras
uv run uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Validation

```bash
cd backend
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
uv run pytest
```

```bash
cd frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run e2e
```

## Runtime behavior

Runs remain available while the backend process is alive. Each required provider failure ends that run while retaining the outputs completed earlier. Model-generated Markdown renders with raw HTML disabled, and provider credentials remain server-side.

The SSE transport follows MDN Web Docs, “Using server-sent events” ([https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)). FastAPI streaming behavior is documented at FastAPI, “Custom Responses and StreamingResponse” ([https://fastapi.tiangolo.com/advanced/custom-response/](https://fastapi.tiangolo.com/advanced/custom-response/)).

## Settings: agent roles library

The **Settings** view (link in the header) lets you manage a reusable library of agent roles:

- **Default number of roles** — a value between 3 and 5 used by the role planner and as the number of library roles selected for a saved panel.
- **CRUD of agent roles** — create, edit, and delete up to 100 saved roles. Each role has a `name`, `focus`, `bias`, and an optional free-form `prompt` that is forwarded to the expert alongside the role mandate (kept in the untrusted user payload, never as a system prompt).
- **Use saved roles** — toggle in the composer to ask the backend to snapshot the first *n* saved roles, where *n* is the default count. The toggle remains disabled until the library contains a complete panel.

The library persists to `backend/data/roles.json` (configurable via the `ROLES_FILE` env var) so it survives backend restarts. Invalid files are preserved with an `.invalid` suffix and replaced with safe defaults. JSON persistence is intended for the app's single-process local deployment. When the toggle is off, the model plans exactly the configured 3–5 roles.
