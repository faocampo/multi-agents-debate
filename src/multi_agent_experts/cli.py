"""Command-line entry point for multi-agent analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from .analyzer import MultiAgentAnalyzer, SwarmError
from .client import ChatClientError, HTTPChatClient
from .models import SwarmConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="multi-agent-experts",
        description="Analyze a decision through conflicting independent expert roles.",
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Decision or question to analyze. If omitted, read it from stdin.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("MAE_ENDPOINT", "http://localhost:11434/api/chat"),
        help="Ollama or OpenAI-compatible chat endpoint (env: MAE_ENDPOINT).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MAE_MODEL"),
        help="Model name (env: MAE_MODEL).",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MAE_API_KEY"),
        help="Optional bearer token (env: MAE_API_KEY).",
    )
    parser.add_argument("--min-roles", type=int, default=3)
    parser.add_argument("--max-roles", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--no-debate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    task = " ".join(args.task).strip()
    if not task and not sys.stdin.isatty():
        task = sys.stdin.read().strip()
    if not task:
        parser.error("provide a task as arguments or through stdin")
    if not args.model:
        parser.error("provide --model or set MAE_MODEL")

    try:
        config = SwarmConfig(
            min_roles=args.min_roles,
            max_roles=args.max_roles,
            max_workers=args.workers,
            include_debate=not args.no_debate,
        )
        client = HTTPChatClient(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
        )
        result = MultiAgentAnalyzer(client, config).analyze(task)
    except (ValueError, SwarmError, ChatClientError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(result.synthesis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

