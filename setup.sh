#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

E2E=false
if [ "${1:-}" = "--e2e" ]; then
  E2E=true
elif [ $# -gt 0 ]; then
  echo "Usage: $0 [--e2e]" >&2
  exit 1
fi

log() {
  echo "[setup] $1"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

check_python() {
  if ! command_exists python3; then
    echo "Error: python3 is not installed. Please install Python 3.12 or newer." >&2
    exit 1
  fi
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    python3 --version >&2
    echo "Error: Python 3.12 or newer is required." >&2
    exit 1
  fi
}

check_uv() {
  if ! command_exists uv; then
    echo "Error: uv is not installed. See https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
  fi
}

check_node() {
  if ! command_exists node || ! command_exists npm; then
    echo "Error: node and npm are not installed. Please install a current Node.js LTS release." >&2
    exit 1
  fi
}

main() {
  check_python
  check_uv
  check_node

  log "Python: $(python3 --version)"
  log "uv: $(uv --version)"
  log "Node: $(node --version)"
  log "npm: $(npm --version)"

  if [ ! -f ".env" ]; then
    log "Creating .env from .env.example"
    cp .env.example .env
    log "Remember to edit .env and set LLM_API_KEY before running ./start.sh"
  else
    log ".env already exists, skipping"
  fi

  log "Ensuring backend/data directory exists"
  mkdir -p backend/data

  log "Installing backend dependencies..."
  (cd backend && uv sync --all-extras)

  log "Installing frontend dependencies..."
  (cd frontend && npm install)

  if [ "$E2E" = true ]; then
    log "Installing Playwright browsers for end-to-end tests..."
    (cd frontend && npx playwright install --with-deps)
  fi

  log "Setup complete."
  log "Next steps:"
  log "  1. Edit .env and set your LLM_API_KEY"
  log "  2. Run ./start.sh"
}

main
