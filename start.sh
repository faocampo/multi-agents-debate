#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

LOGS_DIR="logs"
mkdir -p "$LOGS_DIR"

start_service() {
  local name=$1
  local dir=$2
  local pid_file=$3
  shift 3

  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name is already running (PID $(cat "$pid_file"))"
    return 0
  fi

  rm -f "$pid_file"
  echo "Starting $name..."

  nohup bash -c 'cd "$1" && shift && exec "$@"' bash "$dir" "$@" \
    > "$LOGS_DIR/$name.log" 2>&1 < /dev/null &

  local pid=$!
  echo "$pid" > "$pid_file"
  echo "$name started (PID $pid)"
}

start_service "backend" "backend" ".backend.pid" \
  uv run uvicorn app.main:app --reload --port 8000

start_service "frontend" "frontend" ".frontend.pid" \
  npm run dev

echo
echo "Both services are starting."
echo "Logs: $LOGS_DIR/backend.log, $LOGS_DIR/frontend.log"
echo "Open http://localhost:5173"
