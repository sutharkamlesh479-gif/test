"""OMEGA command line interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from . import __version__
from .analyzers import analyze_file, compare_files
from .events import analyze_events
from .report import write_html


def _write_json(report: dict[str, Any], destination: str | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if destination:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"JSON report written: {path}")
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omega", description="AURIX OMEGA local cyber investigation tools.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect a file as data; do not execute it.")
    inspect.add_argument("file")
    inspect.add_argument("--output", "-o")
    events = commands.add_parser("events", help="Analyze exported JSON or JSONL event logs.")
    events.add_argument("file")
    events.add_argument("--output", "-o")
    diff = commands.add_parser("diff", help="Compare two artifact files.")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--output", "-o")
    report = commands.add_parser("report", help="Render a JSON report to self-contained HTML.")
    report.add_argument("json_file")
    report.add_argument("--html", required=True)
    serve = commands.add_parser("serve", help="Start the local, loopback-only browser dashboard.")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            _write_json(analyze_file(args.file), args.output)
        elif args.command == "events":
            _write_json(analyze_events(args.file), args.output)
        elif args.command == "diff":
            _write_json(compare_files(args.before, args.after), args.output)
        elif args.command == "report":
            value = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("JSON report root must be an object.")
            print(f"HTML report written: {write_html(value, args.html)}")
        elif args.command == "serve":
            if not 1024 <= args.port <= 65535:
                raise ValueError("Choose a port between 1024 and 65535.")
            from .web import serve as serve_web
            serve_web(args.port)
    except (OSError, ValueError) as exc:
        print(f"omega: error: {exc}", file=sys.stderr)
        return 2
    return 0
