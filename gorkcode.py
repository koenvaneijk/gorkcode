#!/usr/bin/env python3
from __future__ import annotations

VERSION: Final[int] = 2
APP_NAME: Final[str] = "gorkcode"

import ast
import datetime
import difflib
import glob
import json
import math
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from re import Match
from typing import Any, Dict, Final, List, Optional, Tuple, Union

# Configuration
MODEL: Final[str] = os.getenv("XAI_MODEL", "grok-4.20-beta-latest-reasoning")
INPUT_PRICE: Final[float] = 2.00 / 1_000_000   # input
CACHED_PRICE: Final[float] = 0.20 / 1_000_000  # cached input
OUTPUT_PRICE: Final[float] = 6.00 / 1_000_000  # output
MAX_FILE_SIZE: Final[int] = 100 * 1024  # 100KB
MAX_LINE_LENGTH: Final[int] = 500
MAX_TOOL_LOOPS: Final[int] = 24

TOOLS: Final[list[dict[str, Any]]] = [
    {
        "type": "function",
        "name": "request_files",
        "description": "Read one or more files from the repository and return their contents. Use this before editing when you need more context.",
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Repository-relative file paths to read",
                }
            },
            "required": ["paths"],
        },
    },
    {
        "type": "function",
        "name": "drop_files",
        "description": "Drop one or more files from the loaded context set.",
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Repository-relative file paths to drop",
                }
            },
            "required": ["paths"],
        },
    },
    {
        "type": "function",
        "name": "create_file",
        "description": "Create a new text file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository-relative file path"},
                "content": {"type": "string", "description": "Full file contents"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "type": "function",
        "name": "edit_file",
        "description": "Apply one exact find/replace edit to an existing text file. The find text must match exactly, including whitespace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository-relative file path"},
                "find": {"type": "string", "description": "Exact text to replace"},
                "replace": {"type": "string", "description": "Replacement text; empty string deletes the match"},
            },
            "required": ["path", "find", "replace"],
        },
    },
    {
        "type": "function",
        "name": "run_shell_command",
        "description": "Run one shell command locally. The user will be asked to approve it first.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "A single shell command"},
            },
            "required": ["command"],
        },
    },
    {
        "type": "function",
        "name": "commit_changes",
        "description": "Create a git commit for all current changes with a concise commit message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Git commit message"},
            },
            "required": ["message"],
        },
    },
]


def ansi(code: str) -> str:
    """Return ANSI escape sequence."""
    return f"\033[{code}"


def styled(text: str, style: str) -> str:
    """Wrap text with ANSI style codes."""
    return f"{ansi(style)}{text}{ansi('0m')}"


def run(shell_cmd: str) -> Optional[str]:
    """Run shell command and return stripped output or None on error."""
    try:
        return subprocess.check_output(
            shell_cmd, shell=True, text=True, stderr=subprocess.STDOUT
        ).strip()
    except Exception:
        return None


_TMUX_WIN: Optional[str] = run("tmux display-message -p '#{window_id}' 2>/dev/null")


def title(t: str) -> None:
    """Set terminal title (and tmux window name if applicable)."""
    print(f"\033]0;{t}\007", end="", flush=True)
    if _TMUX_WIN:
        run(f"tmux rename-window -t {_TMUX_WIN} {t!r} 2>/dev/null")


def render_md(text: str) -> str:
    parts = re.split(r"(```[\s\S]*?```|`[^`\n]+`)", text)
    result = []
    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            inner = part[3:-3]
            if inner.startswith("\n"):
                inner = inner[1:]
            elif "\n" in inner:
                inner = inner.split("\n", 1)[1]
            inner_lines = inner.split("\n")
            inner = "\n".join(f"{line}{ansi('K')}" for line in inner_lines) + ansi("K")
            result.append(f"\n{ansi('48;5;236;37m')}{inner}{ansi('0m')}")
        elif part.startswith("`") and part.endswith("`"):
            result.append(f"{ansi('48;5;236m')}{part[1:-1]}{ansi('0m')}")
        else:
            part = re.sub(
                r"\[([^\]]+)\]\(([^)]+)\)",
                lambda m: f"\033]8;;{m.group(2)}\033\\{ansi('4;34m')}{m.group(1)}{ansi('0m')}\033]8;;\033\\",
                part,
            )
            part = re.sub(r"\*\*(.+?)\*\*", lambda m: f"{ansi('1m')}{m.group(1)}{ansi('22m')}", part)
            part = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", lambda m: f"{ansi('3m')}{m.group(1)}{ansi('23m')}", part)
            part = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", lambda m: f"{ansi('3m')}{m.group(1)}{ansi('23m')}", part)

            def format_header(m: Match[str]) -> str:
                level, text_ = len(m.group(1)), m.group(2)
                if level == 1:
                    return f"{ansi('1;4;33m')}{text_}{ansi('0m')}"
                if level == 2:
                    return f"{ansi('1;33m')}{text_}{ansi('0m')}"
                return f"{ansi('33m')}{text_}{ansi('0m')}"

            part = re.sub(r"^(#{1,3}) (.+)$", format_header, part, flags=re.MULTILINE)
            result.append(part)
    return "".join(result)


def truncate(lines: List[str], n: int = 50, max_line_len: int = MAX_LINE_LENGTH) -> List[str]:
    def trunc_line(line: str) -> str:
        return line if len(line) <= max_line_len else line[:max_line_len] + "..."

    lines = [trunc_line(line) for line in lines]
    return lines if len(lines) <= n else lines[:10] + ["[TRUNCATED]"] + lines[-40:]


_CACHED_SYSTEM_INFO: Optional[Dict[str, Any]] = None


def system_summary() -> Dict[str, Any]:
    """Return cached system info dict."""
    global _CACHED_SYSTEM_INFO
    if _CACHED_SYSTEM_INFO is not None:
        return _CACHED_SYSTEM_INFO
    try:
        tools = [
            "apt",
            "bash",
            "curl",
            "docker",
            "gcc",
            "git",
            "make",
            "node",
            "npm",
            "perl",
            "pip",
            "python3",
            "sh",
            "tar",
            "unzip",
            "wget",
            "zip",
        ]
        versions = {
            tool: (run(f"{tool} --version") or "").split("\n")[0][:80]
            for tool in ["git", "python3", "pip", "node", "npm", "docker", "gcc"]
            if shutil.which(tool)
        }
        _CACHED_SYSTEM_INFO = {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "cwd": os.getcwd(),
            "shell": os.environ.get("SHELL") or os.environ.get("ComSpec") or "",
            "path": os.environ.get("PATH", ""),
            "venv": bool(os.environ.get("VIRTUAL_ENV") or sys.prefix != sys.base_prefix),
            "tools": [tool for tool in tools if shutil.which(tool)],
            "versions": {k: v for k, v in versions.items() if v},
        }
    except Exception:
        _CACHED_SYSTEM_INFO = {}
    return _CACHED_SYSTEM_INFO





def safe_repo_path(root: str, rel_path: str) -> Path:
    """Ensure path is within repo root (prevents escapes)."""
    p = Path(root, rel_path)
    resolved = p.resolve(strict=False)
    root_resolved = Path(root).resolve()
    if not str(resolved).startswith(str(root_resolved)):
        raise ValueError(f"path escapes repo: {rel_path}")
    return p


def safe_read_file(
    path: str, root: Optional[str] = None, confirm_large: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Safely read file with size/symlink/binary checks."""
    p = Path(path) if root is None else safe_repo_path(root, path)
    if not p.exists():
        return None, "not found"
    if p.is_symlink():
        try:
            target = p.resolve()
            root_path = Path(root).resolve() if root else Path.cwd().resolve()
            if not str(target).startswith(str(root_path)):
                return None, f"symlink points outside repo: {target}"
        except (OSError, ValueError) as e:
            return None, f"symlink error: {e}"
    try:
        mode = p.stat().st_mode
        if not stat.S_ISREG(mode):
            return None, "special file (not regular)"
    except OSError as e:
        return None, f"cannot stat: {e}"
    try:
        size = p.stat().st_size
        if size > MAX_FILE_SIZE:
            size_kb = size / 1024
            size_str = f"{size_kb:.1f}KB" if size_kb < 1024 else f"{size_kb / 1024:.1f}MB"
            if confirm_large:
                print(styled(f"Warning: {path} is {size_str} (>{MAX_FILE_SIZE // 1024}KB)", "93m"))
                try:
                    answer = input("Load anyway? (y/n): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    answer = "n"
                if answer != "y":
                    return None, f"skipped (too large: {size_str})"
            else:
                return None, f"file too large: {size_str}"
    except OSError as e:
        return None, f"cannot check size: {e}"
    try:
        content = p.read_text()
        return content if content else "[empty]", None
    except PermissionError:
        return None, "permission denied"
    except UnicodeDecodeError:
        return None, "binary/not UTF-8"
    except OSError as e:
        return None, f"read error: {e}"


def get_map(root: str, max_files: int = 100) -> str:
    binary_ext = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".bmp",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".zip",
        ".tar",
        ".gz",
        ".rar",
        ".7z",
        ".pdf",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".pyc",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    }
    exclude_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        "venv",
        ".venv",
        ".tox",
        "dist",
        "build",
        ".eggs",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
        ".coverage",
        "env",
        ".env",
    }
    files = (run(f"git -C {root} ls-files") or "").splitlines()
    if not files:
        files = [
            str(p.relative_to(root))
            for p in Path(root).rglob("*")
            if p.is_file() and not any(ex in p.parts for ex in exclude_dirs)
        ]
    files = sorted(files, key=lambda f: (f.count("/"), f))[:max_files]
    output = []
    for f in files:
        p = Path(root, f)
        if not p.exists():
            continue
        if p.suffix.lower() in binary_ext:
            output.append(f"{f} [binary]")
            continue
        defs = ""
        if f.endswith(".py"):
            try:
                defs = ": " + ", ".join(
                    n.name
                    for n in ast.parse(p.read_text()).body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                )[:80]
            except Exception:
                pass
        output.append(f"{f}{defs}")
    return "\n".join(output)


def run_shell_interactive(cmd: str) -> Tuple[List[str], int]:
    output_lines = []
    process = subprocess.Popen(
        cmd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            output_lines.append(line.rstrip("\n"))
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=2)
        except Exception:
            pass
        output_lines.append("[INTERRUPTED]")
        print("\n[INTERRUPTED]")
    return output_lines, process.returncode


def lint_py(path: str, content: str) -> Tuple[bool, Optional[str]]:
    if not path.endswith(".py"):
        return True, None
    try:
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, str(e)


class Spinner:
    def __init__(self, label: str = "øgork") -> None:
        self.label: str = label
        self.stop_event: threading.Event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        def spin() -> None:
            print()
            while not self.stop_event.is_set():
                wave = (math.sin(time.time() * 4) + 1) / 2
                rgb_val = int(wave * 255)
                color_code = f"\033[1m\033[38;2;{rgb_val};{rgb_val};{rgb_val}m"
                reset_code = "\033[0m"
                print(f"\r{styled(' øgork ', '48;2;255;255;255;30m')} {color_code}ø{reset_code} ", end="", flush=True)
                time.sleep(0.05)

        self.thread = threading.Thread(target=spin, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join()
        print("\r", end="", flush=True)


class GorkCode:
    def __init__(self) -> None:
        self.repo_root: str = run("git rev-parse --show-toplevel") or os.getcwd()
        self.context_files: set[str] = set()
        self.pending_notes: List[str] = []
        self.previous_response_id: Optional[str] = None
        self.last_usage: Optional[Dict[str, Any]] = None
        self.session_cost: float = 0.0

    def xai_request(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            print(styled("Error: XAI_API_KEY environment variable not set.", "31m"))
            print(styled("To fix this, set your xAI API key:", "93m"))
            print(styled("  export XAI_API_KEY='your-api-key-here'", "37m"))
            print(styled("Get your API key at: https://console.x.ai/", "90m"))
            return None

        req = urllib.request.Request(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"gorkcode/{VERSION}",
            },
            data=json.dumps(payload).encode(),
        )

        spinner = Spinner()
        spinner.start()
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                self.last_usage = body.get("usage")
                if self.last_usage:
                    inp = self.last_usage.get("input_tokens", 0)
                    cached = self.last_usage.get("input_tokens_details", {}).get("cached_tokens", 0)
                    outp = self.last_usage.get("output_tokens", 0)
                    input_c = ((inp or 0) - cached) * INPUT_PRICE + cached * CACHED_PRICE
                    output_c = (outp or 0) * OUTPUT_PRICE
                    self.session_cost += input_c + output_c
                spinner.stop()
                print(f"{styled(' øgork ', '48;2;255;255;255;30m')} {styled('done', '90m')}\n")
                return body
        except urllib.error.HTTPError as e:
            spinner.stop()
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                pass
            print(styled(f"HTTP {e.code}: {e.reason}", "31m"))
            if error_body:
                print(styled(error_body, "31m"))
            return None
        except KeyboardInterrupt:
            spinner.stop()
            print(styled("[user interrupted]", "93m"))
            return None
        except Exception as e:
            spinner.stop()
            print(styled(f"Err: {e}", "31m"))
            return None

    def build_turn_input(self, request: str) -> List[Dict[str, Any]]:
        now = datetime.datetime.now().astimezone()
        day = now.day
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        current_time = now.strftime(f"%A {day}{suffix} of %B %Y, %H:%M %Z")

        files_block = []
        for f in sorted(self.context_files):
            if not Path(self.repo_root, f).exists():
                continue
            content, error = safe_read_file(f, self.repo_root, confirm_large=False)
            body = content if error is None else f"[{error}]"
            files_block.append(f"File: {f}\n```\n{body}\n```")

        parts = [
            f"### Repo Map\n{get_map(self.repo_root)}",
            f"### Loaded Files\n{', '.join(sorted(self.context_files)) if self.context_files else '[none]'}",
        ]
        if files_block:
            parts.append("### File Contents\n" + "\n".join(files_block))
        if self.pending_notes:
            parts.append("### Extra Context\n" + "\n\n".join(self.pending_notes))
            self.pending_notes.clear()

        parts.append(f"### System Summary\n{json.dumps(system_summary(), separators=(',', ':'))}")
        parts.append(f"### Current Time\n{current_time}")
        parts.append(f"### Request\n{request}")

        return [
            {
                "role": "system",
                "content": (
                    "You are a coding expert working inside a local repository tool.\n\n"
                    "Use tools via function calls. Never output XML, markdown code blocks, or any other format for tool calls.\n\n"
                    "Behavior rules:\n"
                    "- Think step by step before deciding to use tools.\n"
                    "- Answer normally when no tool is needed.\n"
                    "- Always read relevant files using request_files before editing them (unless creating a brand new file).\n"
                    "- Prefer small, precise edits. Make the 'find' string as short and unique as possible.\n"
                    "- Preserve original formatting, whitespace, and surrounding code style exactly.\n"
                    "- If an edit's exact find text is not found, read the file again and use a more precise match.\n"
                    "- Only run shell commands when genuinely necessary.\n"
                    "- After changes, call commit_changes with a short message if and only if files were actually modified.\n"
                    "- Keep all user-facing answers concise.\n\n"
                    "Important: When calling tools, output raw JSON. "
                    "Do not escape any quotes inside the JSON arguments. Output raw double quotes."
                ),
            },
            {"role": "user", "content": "\n\n".join(parts)},
        ]

    def extract_text(self, response: Dict[str, Any]) -> str:
        texts = []
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") in ("output_text", "text"):
                    text = content.get("text", "")
                    if text:
                        texts.append(text)
        return "\n".join(texts).strip()

    def extract_function_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        calls = []
        for item in response.get("output", []):
            if item.get("type") == "function_call":
                calls.append(item)
        return calls

    def print_assistant_text(self, text: str) -> None:
        if not text:
            return
        print(render_md(text))
        print()

    def tool_request_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        paths = args["paths"]
        results = []
        added = []
        for path in paths:
            path = path.strip()
            if not path:
                continue
            content, error = safe_read_file(path, self.repo_root, confirm_large=True)
            if error:
                results.append({"path": path, "ok": False, "error": error})
                print(styled(f"✗ {path}", "31m"))
                print(styled(f"  {error}", "90m"))
            else:
                self.context_files.add(path)
                added.append(path)
                results.append({"path": path, "ok": True, "content": content})
                print(styled(f"✓ {path}", "32m"))
                if content and len(content) > 60:
                    preview = content.splitlines()[0][:80]
                    tokens = len(content) // 4
                    print(styled(f"  {len(content):,} chars • {len(content.splitlines())} lines • ~{tokens:,} tokens", "90m"))
        if added:
            print(styled(f"+{len(added)} file(s) loaded", "93m"))
        elif not results:
            print(styled("No valid paths provided", "33m"))
        return {"files": results}

    def tool_drop_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        removed = []
        for path in args["paths"]:
            path = path.strip()
            if path in self.context_files:
                self.context_files.discard(path)
                removed.append(path)
        return {"removed": removed}

    def tool_create_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args["path"]
        content = args["content"]
        try:
            p = safe_repo_path(self.repo_root, path)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        if p.exists():
            return {"ok": False, "error": "file already exists"}

        ok, lint_error = lint_py(path, content)
        if not ok:
            print(styled(f"Lint Fail {path}: {lint_error}", "31m"))
            return {"ok": False, "error": f"python syntax error: {lint_error}"}

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            self.context_files.add(path)
            for ln in content.splitlines():
                print(styled(f"+{ln}", "32m"))
            print(styled(f"Created {path}", "32m"))
            return {"ok": True, "path": path}
        except (PermissionError, OSError) as e:
            return {"ok": False, "error": str(e)}

    def tool_edit_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args["path"]
        find = args["find"]
        replace = args["replace"]

        try:
            p = safe_repo_path(self.repo_root, path)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        if not p.exists():
            return {"ok": False, "error": "file not found"}

        content, error = safe_read_file(path, self.repo_root, confirm_large=False)
        if error:
            return {"ok": False, "error": error}
        if content == "[empty]":
            content = ""

        if find not in content:
            return {"ok": False, "error": "exact find text not found"}

        new_content = content.replace(find, replace, 1)
        ok, lint_error = lint_py(path, new_content)
        if not ok:
            print(styled(f"Lint Fail {path}: {lint_error}", "31m"))
            return {"ok": False, "error": f"python syntax error: {lint_error}"}

        if new_content == content:
            return {"ok": False, "error": "no-op edit"}

        diff_lines = list(
            difflib.unified_diff(
                content.splitlines(),
                new_content.splitlines(),
                fromfile=path,
                tofile=path,
                lineterm="",
            )
        )
        for d in diff_lines:
            if d.startswith(("---", "+++")):
                continue
            color = "32m" if d.startswith("+") else "31m" if d.startswith("-") else "0m"
            print(styled(d, color))

        try:
            p.write_text(new_content)
            self.context_files.add(path)
            print(styled(f"Applied {path}", "32m"))
            return {"ok": True, "path": path, "diff": truncate(diff_lines)}
        except (PermissionError, OSError) as e:
            return {"ok": False, "error": str(e)}

    def tool_run_shell_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        cmd = args["command"].strip()
        if not cmd:
            return {"ok": False, "error": "empty command"}

        print(f"{styled(' øgork ', '48;2;255;255;255;30m')} wants to run:\n")
        print(f"  {styled(f'$ {cmd}', '48;5;236;37m')}\n")
        title(f"⏳ {APP_NAME}")
        print(styled("run? (y/n): ", "1m"), end="")
        sys.stdout.flush()
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            answer = "n"

        if answer != "y":
            return {"ok": False, "denied": True, "error": "user denied"}

        try:
            output_lines, exit_code = run_shell_interactive(cmd)
            print(f"{styled('exit=', '31m')}{exit_code}\n")
            return {
                "ok": True,
                "command": cmd,
                "exit_code": exit_code,
                "output": "\n".join(truncate(output_lines)),
            }
        except Exception as e:
            return {"ok": False, "command": cmd, "error": str(e)}

    def tool_commit_changes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        message = args["message"].strip()
        if not message:
            return {"ok": False, "error": "empty commit message"}

        status = run(f"git -C {self.repo_root} status --porcelain")
        if not status:
            return {"ok": False, "error": "nothing to commit"}

        output = run(
            f"git -C {self.repo_root} add -A && git -C {self.repo_root} commit -m {message!r}"
        )
        if output is None:
            return {"ok": False, "error": "git commit failed"}
        print(styled(output, "32m"))
        return {"ok": True, "message": message, "git": output}

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "request_files":
            return self.tool_request_files(args)
        if name == "drop_files":
            return self.tool_drop_files(args)
        if name == "create_file":
            return self.tool_create_file(args)
        if name == "edit_file":
            return self.tool_edit_file(args)
        if name == "run_shell_command":
            return self.tool_run_shell_command(args)
        if name == "commit_changes":
            return self.tool_commit_changes(args)
        return {"ok": False, "error": f"unknown tool: {name}"}

    def run_agent_turn(self, request: str) -> None:
        response = self.xai_request(
            {
                "model": MODEL,
                "input": self.build_turn_input(request),
                "tools": TOOLS,
                "parallel_tool_calls": True,
                "store": True,
                **(
                    {"previous_response_id": self.previous_response_id}
                    if self.previous_response_id
                    else {}
                ),
            }
        )
        if not response:
            return

        self.previous_response_id = response.get("id") or self.previous_response_id

        loops = 0
        while True:
            loops += 1
            if loops > MAX_TOOL_LOOPS:
                print(styled("Stopped: too many tool loops.", "31m"))
                return

            text = self.extract_text(response)
            if text:
                self.print_assistant_text(text)

            calls = self.extract_function_calls(response)
            if not calls:
                return

            tool_outputs = []
            for call in calls:
                name = call.get("name")
                raw_args = call.get("arguments", "{}")
                call_id = call.get("call_id")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception as e:
                    result = {"ok": False, "error": f"invalid JSON arguments: {e}"}
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(result),
                        }
                    )
                    continue

                print(
                    f"{styled(' øgork ', '48;2;255;255;255;30m')} "
                    f"{styled(name, '1;36m')} "
                    f"{styled(json.dumps(args, ensure_ascii=False), '90m')}"
                )
                result = self.execute_tool(name, args)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            response = self.xai_request(
                {
                    "model": MODEL,
                    "input": tool_outputs,
                    "tools": TOOLS,
                    "parallel_tool_calls": True,
                    "store": True,
                    "previous_response_id": self.previous_response_id,
                }
            )
            if not response:
                return
            self.previous_response_id = response.get("id") or self.previous_response_id

    def cmd_add(self, pattern: str) -> None:
        found = [
            f
            for f in glob.glob(pattern, root_dir=self.repo_root, recursive=True)
            if Path(self.repo_root, f).is_file()
        ]
        added, skipped = [], []
        for f in found:
            content, error = safe_read_file(f, self.repo_root, confirm_large=True)
            if error:
                print(styled(f"Skip {f}: {error}", "31m"))
                skipped.append(f)
            else:
                self.context_files.add(f)
                added.append(f)
        print(f"Added {len(added)} files" + (f", skipped {len(skipped)}" if skipped else ""))

    def cmd_roast(self) -> None:
        self.run_agent_turn("Roast this repository. Be specific and technical.")

    def cmd_status(self) -> None:
        print(styled(f"Repository: {self.repo_root}", "36m"))
        print(styled(f"Loaded: {len(self.context_files)} file(s)", "36m"))
        if self.context_files:
            for f in sorted(self.context_files)[:8]:
                print(styled(f"  • {f}", "90m"))
            if len(self.context_files) > 8:
                print(styled(f"  ... +{len(self.context_files)-8} more", "90m"))
        if self.previous_response_id:
            print(styled("Conversation: active", "32m"))
        print(styled(f"Model: {MODEL}", "90m"))

    def shell_user_command(self, shell_cmd: str) -> None:
        output_lines, exit_code = run_shell_interactive(shell_cmd)
        print(f"\n{styled(f'exit={exit_code}', '90m')}")
        title(f"❓ {APP_NAME}")
        try:
            answer = input("\aAdd to context? [t]runcated/[f]ull/[n]o: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            answer = "n"

        if answer in ("t", "f"):
            body = "\n".join(truncate(output_lines) if answer == "t" else output_lines)
            self.pending_notes.append(f"$ {shell_cmd}\nexit={exit_code}\n{body}")
            print(styled("Added to context", "93m"))

    def repl(self) -> None:
        print(
            f"{styled(' øgork ', '48;2;255;255;255;30m')}"
            f"{styled(' code ', '48;5;236;37m')}"
            f" {styled(' ' + MODEL + ' ', '48;5;236;37m')}"
            f" {styled(' ctrl+d to send ', '48;5;236;37m')}"
        )

        while True:
            title(f"❓ {APP_NAME}")
            last = self.last_usage or {}
            ctx_est = len(self.context_files) * 300
            inp = last.get("input_tokens", 0)
            outp = last.get("output_tokens", 0)
            cached = last.get("input_tokens_details", {}).get("cached_tokens", 0)
            cache_pct = f"{int(cached / inp * 100) if inp > 0 else 0}%"

            input_cost = ((inp or 0) - cached) * INPUT_PRICE + cached * CACHED_PRICE
            output_cost = (outp or 0) * OUTPUT_PRICE
            total_cost = input_cost + output_cost

            u = f"ctx:~{ctx_est:,} • {inp:,}↑({cache_pct} cached) • {outp:,}↓(${total_cost:.2f}/${self.session_cost:.2f})"
            print(styled(u, "90m"))
            print(f"\a{styled('❯ ', '40;37m')}", end="", flush=True)
            input_lines = []
            try:
                while True:
                    input_lines.append(input())
            except EOFError:
                if not input_lines:
                    print("\nAd astra!")
                    title("")
                    break
            except KeyboardInterrupt:
                print()
                continue

            user_input = "\n".join(input_lines).strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                command, _, arg = user_input.partition(" ")
                if command == "/exit":
                    print("Bye!")
                    title("")
                    break
                elif command == "/add":
                    self.cmd_add(arg)
                elif command == "/drop":
                    self.context_files.discard(arg)
                elif command == "/clear":
                    self.previous_response_id = None
                    self.pending_notes.clear()
                    self.session_cost = 0.0
                    print("Conversation cleared.")
                elif command == "/undo":
                    out = run(f"git -C {self.repo_root} reset --soft HEAD~1")
                    if out:
                        print(out)
                elif command == "/roast":
                    self.cmd_roast()
                elif command == "/status":
                    self.cmd_status()
                elif command == "/help":
                    print("/add <glob> - Add files")
                    print("/drop <file> - Remove file")
                    print("/status - Show context & repo info")
                    print("/clear - Clear conversation")
                    print("/undo - Undo commit")
                    print("/roast - Roast repo")
                    print("/exit - Exit")
                    print("!<cmd> - Shell")
                continue

            if user_input.startswith("!"):
                shell_cmd = user_input[1:].strip()
                if shell_cmd:
                    self.shell_user_command(shell_cmd)
                continue

            self.run_agent_turn(user_input)


def main() -> None:
    GorkCode().repl()


if __name__ == "__main__":
    main()
