# AI Swarm Analysis

A local decision-analysis application that assembles three to five independent expert lenses, optionally lets them debate, stress-tests their shared assumptions, and produces a conflict-preserving synthesis.

## Features

- **Decision composer** — submit a decision, optionally enable the debate round and clarifying questions, and start the analysis.
- **Live stage timeline** — watch role planning, independent experts, rebuttals, devil’s advocate, and synthesis update in real time via Server-Sent Events.
- **Expert cards** — each role’s opinion, debate response, and contribution to the final verdict is displayed separately.
- **Session history** — reopen runs from the current server session.
- **Markdown export** — download the complete analysis as a Markdown file from the result view.
- **Role library** — save reusable agent roles and choose the provider model from the OpenRouter `/v1/models` list.
- **Clarifying questions** — when enabled, the orchestrator asks up to five follow-up questions before designing the expert panel.

## Architecture

- `backend/`: Python 3.12, FastAPI, Pydantic v2, `httpx`, in-memory runs, and Server-Sent Events.
- `frontend/`: React 19, TypeScript, and Vite single-page interface.
- `e2e/`: deterministic fake OpenAI-compatible provider for local integration testing.
- `frontend/e2e/`: Playwright integration workflow.
- `docs/PLAN.md`: the original product and technical specification that shaped the implementation.
- `outputs/ai-swarm-framework-spec.md`: complete product and technical reference.
- `multi-agents-debate.code-workspace`: VS Code / Windsurf workspace configuration.
- `setup.sh`: one-command dependency installer.
- `start.sh` / `stop.sh`: convenience scripts to launch or stop the backend and frontend together.

The backend calls any OpenAI-compatible `/v1/chat/completions` endpoint. The default configuration targets [OpenRouter](https://openrouter.ai/); its model list and Zero Data Retention endpoints are documented in the OpenRouter docs. You can switch to any compatible provider by overriding `LLM_BASE_URL` and `LLM_MODEL` in `.env`.

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- A current Node.js LTS release and npm
- An OpenAI-compatible model provider; the defaults use [OpenRouter](https://openrouter.ai/) (`LLM_API_KEY` required)
- bash or a POSIX-compatible shell (for the helper scripts)

## Quick start

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd multi-agents-debate
   ```

2. Install all dependencies and bootstrap the environment:

   ```bash
   ./setup.sh
   ```

   `setup.sh` checks for Python 3.12, `uv`, Node.js, and npm, creates `.env` from `.env.example` when it does not yet exist, ensures `backend/data` exists, then runs `uv sync --all-extras` and `npm install`.

   To also install Playwright browsers for end-to-end tests, run:

   ```bash
   ./setup.sh --e2e
   ```

3. Edit `.env` and set `LLM_API_KEY`:

   ```bash
   # .env was created by setup.sh if it did not exist
   # Replace YOUR_API_KEY with your provider key
   ```

4. Start the backend and frontend:

   ```bash
   ./start.sh
   ```

   Then open [http://localhost:5173](http://localhost:5173).

5. Stop both services with:

   ```bash
   ./stop.sh
   ```

## Configuration

`setup.sh` copies `.env.example` to `.env` automatically, but you can also do it manually:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible chat completions base URL |
| `LLM_API_KEY` | `YOUR_API_KEY` | Provider API key |
| `LLM_MODEL` | `openai/gpt-4o-mini` | Model identifier |
| `LLM_TIMEOUT_SECONDS` | `120` | Per-call timeout |
| `LLM_ORCHESTRATOR_TEMPERATURE` | `0.9` | Role planner temperature |
| `LLM_EXPERT_TEMPERATURE` | `0.7` | Expert round temperature |
| `LLM_DEBATE_TEMPERATURE` | `0.6` | Rebuttal round temperature |
| `LLM_ADVOCATE_TEMPERATURE` | `0.8` | Devil’s advocate temperature |
| `LLM_MERGE_TEMPERATURE` | `0.4` | Synthesis temperature |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origin |
| `ROLES_FILE` | `data/roles.json` | Path to the persisted role library |

## How to use

### Analyze a decision

1. Enter a decision in the composer. Be specific: include context, constraints, and stakes.
2. Choose analysis options:
   - **Include expert debate** — each lens responds to the others before synthesis.
   - **Ask clarifying questions first** — the orchestrator asks up to five follow-up questions; answer or skip them before the panel is planned.
   - **Use saved roles** — reuse the first *n* roles from your saved library (requires a complete panel of `default_role_count` saved roles).
3. Click **Analyze decision**. The live stage timeline shows progress through role planning, independent analysis, rebuttals, devil’s advocate, and synthesis.

### Manage lenses and models

Open **Settings** from the header to:

- **Language model** — choose the provider model from the OpenRouter `/v1/models` list. Optionally filter to Zero Data Retention (ZDR) endpoints. The selection persists with the role library.
- **Default number of roles** — a value between 3 and 5 used by the role planner and as the number of library roles selected for a saved panel.
- **CRUD of agent roles** — create, edit, and delete up to 100 saved roles. Each role has a `name`, `focus`, `bias`, and an optional free-form `prompt` that is forwarded to the expert alongside the role mandate (kept in the untrusted user payload, never as a system prompt).
- **Use saved roles** — toggle in the composer to ask the backend to snapshot the first *n* saved roles, where *n* is the default count. The toggle remains disabled until the library contains a complete panel.

### Review and export results

- **Expert cards** — read each role's independent analysis and, when debate is enabled, its rebuttal.
- **Synthesis** — the final verdict preserves disagreement and explains how the panel converged or diverged.
- **Session history** — select any previous run from the sidebar to reopen it while the backend is running.
- **Markdown export** — download the full analysis as a `.md` file from the result view.

## Validation

Backend:

```bash
cd backend
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
uv run pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run e2e
```

## Runtime behavior

- Runs remain available while the backend process is alive. Each required provider failure ends that run while retaining the outputs completed earlier.
- The stage pipeline is: role planning → (optional) clarification → expert opinions → optional debate rebuttals → devil’s advocate → final synthesis.
- Clarification is available only when the panel is planned by the model (not when using saved roles).
- Model-generated Markdown renders with raw HTML disabled.
- Provider credentials stay server-side; the frontend never stores the API key.
- The role library persists to `backend/data/roles.json` (or the path in `ROLES_FILE`) so it survives backend restarts. Invalid files are preserved with an `.invalid` suffix and replaced with safe defaults. JSON persistence is intended for the app’s single-process local deployment.
- When the **Use saved roles** toggle is off in the composer, the model plans exactly the configured 3–5 roles.

The SSE transport follows MDN Web Docs, “Using server-sent events” ([https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)). FastAPI streaming behavior is documented at FastAPI, “Custom Responses and StreamingResponse” ([https://fastapi.tiangolo.com/advanced/custom-response/](https://fastapi.tiangolo.com/advanced/custom-response/)).

## Open source & tooling

This project is built on and benefits from many open-source projects:

### Backend

- [Python 3.12](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Pydantic v2](https://docs.pydantic.dev/) and [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — data validation and settings
- [httpx](https://www.python-httpx.org/) — HTTP client for provider calls
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [pytest](https://docs.pytest.org/) and [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) — testing
- [mypy](https://mypy.readthedocs.io/) — static type checking
- [ruff](https://docs.astral.sh/ruff/) — linting and formatting
- [uv](https://docs.astral.sh/uv/) — Python package and project manager

### Frontend

- [React 19](https://react.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [Vite](https://vitejs.dev/)
- [react-markdown](https://github.com/remarkjs/react-markdown) and [remark-gfm](https://github.com/remarkjs/remark-gfm) — safe Markdown rendering
- [Vitest](https://vitest.dev/) — unit testing
- [Testing Library](https://testing-library.com/) — React component testing
- [ESLint](https://eslint.org/) and [typescript-eslint](https://typescript-eslint.io/) — linting
- [Playwright](https://playwright.dev/) — end-to-end testing
- [Node.js](https://nodejs.org/) and npm

### Provider

- Defaults to the OpenRouter [OpenAI-compatible chat completions API](https://openrouter.ai/docs/api); compatible with any provider that exposes `/v1/chat/completions`.

## License

See [LICENSE](LICENSE).
