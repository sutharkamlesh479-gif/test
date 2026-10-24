"""Bounded local tools. All paths are confined to the user-selected workspace."""
from __future__ import annotations
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build"}
MAX_TEXT_BYTES = 1_000_000
MAX_FILES = 500

TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "list_files", "description": "List files inside the selected workspace. Paths are relative to the workspace root.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative folder path, default '.'"}}, "required": []}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a UTF-8 text file inside the workspace. Never use this for secrets or binary files.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_files", "description": "Search text in workspace files. Returns matching file names and line snippets.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "path": {"type": "string", "description": "Optional relative folder; default '.'"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or replace a UTF-8 text file inside the selected workspace. Only available when the user explicitly enables file writes in the GUI.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "check_python", "description": "Syntax-check a Python file inside the workspace without executing it.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run tests in the selected workspace using the current Python interpreter and unittest discovery. Runs without a shell and has a timeout.", "parameters": {"type": "object", "properties": {"test_path": {"type": "string", "description": "Optional relative tests folder; default tests"}}, "required": []}}},
    {"type": "function", "function": {"name": "git_status", "description": "Read-only git status for the selected workspace, when it is a Git repository.", "parameters": {"type": "object", "properties": {}, "required": []}}},
]


class ToolError(ValueError):
    pass


class WorkspaceTools:
    def __init__(self, workspace: str | Path, allow_writes: bool = False, allow_execution: bool = False):
        self.workspace = Path(workspace).expanduser().resolve()
        self.allow_writes = allow_writes
        self.allow_execution = allow_execution

    def _resolve(self, rel_path: str = ".") -> Path:
        if not isinstance(rel_path, str) or not rel_path.strip():
            rel_path = "."
        candidate = (self.workspace / rel_path).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError("Path is outside the selected workspace.") from exc
        return candidate

    def _iter_files(self, root: Path):
        if not root.exists():
            raise ToolError(f"Path does not exist: {root.relative_to(self.workspace)}")
        if root.is_file():
            yield root
            return
        count = 0
        for current, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith("."))
            for name in sorted(files):
                path = Path(current) / name
                if path.is_symlink():
                    continue
                count += 1
                if count > MAX_FILES:
                    return
                yield path

    def list_files(self, path: str = ".") -> dict[str, Any]:
        root = self._resolve(path)
        files = []
        for item in self._iter_files(root):
            files.append(str(item.relative_to(self.workspace)).replace("\\", "/"))
            if len(files) >= MAX_FILES:
                break
        return {"root": str(root.relative_to(self.workspace)), "count": len(files), "files": files}

    def read_file(self, path: str) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.is_file():
            raise ToolError("The requested path is not a file.")
        if target.stat().st_size > MAX_TEXT_BYTES:
            raise ToolError("File is larger than the 1 MB text-read limit.")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError("File is not UTF-8 text; binary reading is disabled.") from exc
        return {"path": str(target.relative_to(self.workspace)), "content": text[:30000], "truncated": len(text) > 30000}

    def search_files(self, query: str, path: str = ".") -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ToolError("Search query cannot be empty.")
        root = self._resolve(path)
        matches = []
        scanned = 0
        for item in self._iter_files(root):
            if item.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".exe", ".dll", ".pyc", ".db", ".sqlite"}:
                continue
            try:
                if item.stat().st_size > MAX_TEXT_BYTES:
                    continue
                lines = item.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            for index, line in enumerate(lines, 1):
                if query.casefold() in line.casefold():
                    matches.append({"path": str(item.relative_to(self.workspace)), "line": index, "snippet": line[:240]})
                    if len(matches) >= 100:
                        return {"scanned_files": scanned, "matches": matches, "truncated": True}
        return {"scanned_files": scanned, "matches": matches, "truncated": False}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        if not self.allow_writes:
            raise ToolError("File writes are disabled. Enable 'Allow file changes' in the GUI first.")
        target = self._resolve(path)
        if not target.name or target.is_dir():
            raise ToolError("A file path is required.")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ToolError("File content must be UTF-8 text under 1 MB.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return {"path": str(target.relative_to(self.workspace)), "bytes_written": target.stat().st_size, "success": True}

    def check_python(self, path: str) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.is_file() or target.suffix.lower() != ".py":
            raise ToolError("check_python requires a .py file inside the workspace.")
        if target.stat().st_size > MAX_TEXT_BYTES:
            raise ToolError("File is larger than the syntax-check limit.")
        try:
            ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
        except (SyntaxError, UnicodeDecodeError) as exc:
            return {"success": False, "error": str(exc), "path": str(target.relative_to(self.workspace))}
        return {"success": True, "path": str(target.relative_to(self.workspace)), "message": "Python syntax is valid."}

    def run_tests(self, test_path: str = "tests") -> dict[str, Any]:
        if not self.allow_execution:
            raise ToolError("Test execution is disabled. Enable 'Allow test runs' in the GUI first.")
        target = self._resolve(test_path)
        if not target.exists() or not target.is_dir():
            raise ToolError("Test folder does not exist. Specify an existing relative folder.")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(target), "-v"],
            cwd=str(self.workspace), capture_output=True, text=True, timeout=60, shell=False,
        )
        return {"returncode": proc.returncode, "success": proc.returncode == 0,
                "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:]}

    def git_status(self) -> dict[str, Any]:
        if not (self.workspace / ".git").exists():
            raise ToolError("The selected workspace is not a Git repository.")
        proc = subprocess.run(["git", "status", "--short", "--branch"], cwd=str(self.workspace),
                              capture_output=True, text=True, timeout=15, shell=False)
        return {"returncode": proc.returncode, "stdout": proc.stdout[-5000:], "stderr": proc.stderr[-2000:]}

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(args, dict):
            raise ToolError("Tool arguments must be an object.")
        mapping = {
            "list_files": lambda: self.list_files(**args),
            "read_file": lambda: self.read_file(**args),
            "search_files": lambda: self.search_files(**args),
            "write_file": lambda: self.write_file(**args),
            "check_python": lambda: self.check_python(**args),
            "run_tests": lambda: self.run_tests(**args),
            "git_status": lambda: self.git_status(),
        }
        if name not in mapping:
            raise ToolError(f"Tool is not available: {name}")
        return mapping[name]()
