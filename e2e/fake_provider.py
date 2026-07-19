from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

ROLES = [
    {"name": "Customer Advocate", "focus": "Adoption and retention", "bias": "Protect trust"},
    {"name": "Finance Lead", "focus": "Unit economics", "bias": "Protect runway"},
    {"name": "Systems Engineer", "focus": "Delivery risk", "bias": "Prefer reversibility"},
]


def completion(system: str, user: str) -> str:
    payload: dict[str, Any] = json.loads(user)
    if "design a small panel" in system:
        return json.dumps(ROLES)
    if "one member of a decision-analysis panel" in system:
        return f"## Recommendation\n\nPilot the change through the {payload['role']['name']} lens."
    if "revising a decision analysis" in system:
        return f"## Revised recommendation\n\n{payload['role']['name']} supports a bounded pilot."
    if "devil's advocate" in system:
        return "## Shared assumptions under attack\n\nThe panel may overestimate stable demand."
    if "synthesize a multi-angle" in system:
        return "## Verdict\n\nRun a reversible pilot with explicit success thresholds."
    raise ValueError("unexpected prompt")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        system = request["messages"][0]["content"]
        user = request["messages"][1]["content"]
        if "devil's advocate" in system and "[FAIL_ADVOCATE]" in user:
            self.send_error(503)
            return
        try:
            content = completion(system, user)
        except (KeyError, TypeError, ValueError):
            self.send_error(400)
            return
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 9999), Handler).serve_forever()
