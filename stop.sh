#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

kill_tree() {
  local pid=$1
  local children
  children=$(pgrep -P "$pid" 2>/dev/null || true)

  local child
  for child in $children; do
    if [ -n "$child" ]; then
      kill_tree "$child"
    fi
  done

  kill -TERM "$pid" 2>/dev/null || true
}

stop_service() {
  local name=$1
  local pid_file=$2

  if [ ! -f "$pid_file" ]; then
    echo "$name is not running"
    return 0
  fi

  local pid
  pid=$(cat "$pid_file")

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$name is not running (stale PID file removed)"
    rm -f "$pid_file"
    return 0
  fi

  echo "Stopping $name (PID $pid)..."
  kill_tree "$pid"

  local waited=0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 20 ]; do
    sleep 0.5
    waited=$((waited + 1))
  done

  if kill -0 "$pid" 2>/dev/null; then
    echo "$name did not stop gracefully; forcing kill..."
    kill -KILL "$pid" 2>/dev/null || true
  fi

  rm -f "$pid_file"
  echo "$name stopped"
}

stop_service "backend" ".backend.pid"
stop_service "frontend" ".frontend.pid"
