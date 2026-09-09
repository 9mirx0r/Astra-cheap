#!/usr/bin/env python3
"""Worker seams for local tests and the real Codex CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from astra_contracts import TaskSpec, WorkerResponse


class WorkerError(RuntimeError):
    """A provider failure that should remain visible in the run result."""


class Worker(Protocol):
    def respond(self, prompt: str, task: TaskSpec, turn: int) -> WorkerResponse:
        ...


class ScriptedWorker:
    """Deterministic worker used by runtime tests and offline smoke checks."""

    def __init__(self, responses: Sequence[WorkerResponse | Mapping[str, Any]]):
        self.responses = [
            response if isinstance(response, WorkerResponse) else WorkerResponse.from_mapping(response)
            for response in responses
        ]
        self.prompts: list[str] = []

    def respond(self, prompt: str, task: TaskSpec, turn: int) -> WorkerResponse:
        self.prompts.append(prompt)
        if turn >= len(self.responses):
            return WorkerResponse(kind="error", message="scripted worker exhausted")
        return self.responses[turn]


def _tool_event(data: Mapping[str, Any]) -> bool:
    item_value = data.get("item")
    item: dict[str, Any] = item_value if isinstance(item_value, dict) else {}
    haystack = " ".join(str(data.get(key, "")) for key in ("type", "name", "event"))
    haystack += " " + " ".join(str(item.get(key, "")) for key in ("type", "name"))
    return any(marker in haystack.lower() for marker in ("tool_call", "function_call", "command_execution", "shell_command"))


def _usage_from_events(raw: str) -> dict[str, int]:
    usage: dict[str, int] = {}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        value = event.get("usage")
        if not isinstance(value, dict):
            continue
        input_details = value.get("prompt_tokens_details", {}) or value.get("input_tokens_details", {}) or {}
        output_details = value.get("completion_tokens_details", {}) or {}
        candidates = {
            "input_tokens": value.get("input_tokens", value.get("prompt_tokens", 0)),
            "cached_input_tokens": value.get("cached_input_tokens", input_details.get("cached_tokens", 0)),
            "output_tokens": value.get("output_tokens", value.get("completion_tokens", 0)),
            "reasoning_output_tokens": value.get("reasoning_output_tokens", output_details.get("reasoning_tokens", 0)),
        }
        for key, candidate in candidates.items():
            if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                usage[key] = max(usage.get(key, 0), int(candidate))
    return usage


def _last_json_object(raw: str) -> dict[str, Any] | None:
    for line in reversed(raw.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


class CodexExecWorker:
    """Run a bounded read-only Codex turn and normalize its final JSON object."""

    def __init__(
        self,
        model: str = "gpt-5.6-luna",
        effort: str = "max",
        timeout_seconds: int = 900,
        inactivity_timeout_seconds: int = 300,
        artifact_dir: Path | None = None,
    ):
        self.model = model
        self.effort = effort
        self.timeout_seconds = timeout_seconds
        self.inactivity_timeout_seconds = inactivity_timeout_seconds
        self.artifact_dir = artifact_dir
        self.prompts: list[str] = []
        self._session_started: float | None = None

    def respond(self, prompt: str, task: TaskSpec, turn: int) -> WorkerResponse:
        cli = shutil_which("codex")
        if not cli:
            raise WorkerError("codex executable not found on PATH")
        artifact_dir = (self.artifact_dir or (task.root / ".local" / "astra-runtime")).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        schema_path = artifact_dir / "worker_response.schema.json"
        answer_path = artifact_dir / f"turn-{turn + 1}.answer.json"
        events_path = artifact_dir / f"turn-{turn + 1}.events.jsonl"
        schema_path.write_text(json.dumps(_response_schema(), indent=2), encoding="utf-8")
        prompt_path = artifact_dir / f"turn-{turn + 1}.prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        self.prompts.append(prompt)
        command = [
            cli,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--json",
            "--color",
            "never",
            "--sandbox",
            "read-only",
            "--cd",
            str(task.root),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(answer_path),
            "--model",
            self.model.lower(),
            "-c",
            f"model_reasoning_effort={self.effort}",
            "-",
        ]
        turn_started = time.perf_counter()
        if self._session_started is None:
            self._session_started = turn_started
        timed_out = False
        inactivity_timed_out = False
        returncode: int | None = None
        with prompt_path.open("rb") as prompt_file, events_path.open("wb") as events_file, (
            artifact_dir / f"turn-{turn + 1}.stderr.txt"
        ).open("wb") as stderr_file:
            proc = subprocess.Popen(
                command,
                cwd=str(task.root),
                stdin=prompt_file,
                stdout=events_file,
                stderr=stderr_file,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            last_activity = turn_started
            last_sizes = (0, 0)
            while proc.poll() is None:
                now = time.perf_counter()
                sizes = (
                    events_path.stat().st_size if events_path.exists() else 0,
                    (artifact_dir / f"turn-{turn + 1}.stderr.txt").stat().st_size,
                )
                if sizes != last_sizes:
                    last_sizes = sizes
                    last_activity = now
                if now - self._session_started >= self.timeout_seconds:
                    timed_out = True
                    _terminate_process_tree(proc)
                    break
                if now - last_activity >= self.inactivity_timeout_seconds:
                    timed_out = True
                    inactivity_timed_out = True
                    _terminate_process_tree(proc)
                    break
                time.sleep(1)
            try:
                returncode = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                _terminate_process_tree(proc)
                returncode = proc.wait(timeout=30)

        elapsed_ms = round((time.perf_counter() - turn_started) * 1000, 2)
        stdout = events_path.read_text(encoding="utf-8", errors="replace")
        stderr_path = artifact_dir / f"turn-{turn + 1}.stderr.txt"
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        if timed_out:
            kind = "inactivity" if inactivity_timed_out else "wall-clock"
            raise WorkerError(
                f"Codex worker exceeded {kind} timeout "
                f"({self.inactivity_timeout_seconds if inactivity_timed_out else self.timeout_seconds}s total)\n"
                f"{(stderr + chr(10) + stdout)[-3000:]}"
            )
        usage = _usage_from_events(stdout)
        usage["elapsed_ms"] = int(elapsed_ms)
        usage["event_count"] = sum(1 for line in stdout.splitlines() if line.strip())
        usage["tool_call_count"] = sum(
            1
            for line in stdout.splitlines()
            if line.strip() and _safe_tool_event(line)
        )
        if returncode != 0:
            detail = (stderr + "\n" + stdout)[-3000:]
            raise WorkerError(f"Codex exited with {returncode}: {detail.strip()}")

        answer = answer_path.read_text(encoding="utf-8", errors="replace") if answer_path.is_file() else ""
        data = _last_json_object(answer) or _last_json_object(stdout)
        if data is None:
            raise WorkerError("Codex completed without a JSON worker response")
        data = dict(data)
        data["usage"] = {**usage, **dict(data.get("usage", {}))}
        response = WorkerResponse.from_mapping(data)
        return WorkerResponse(
            kind=response.kind,
            patch=response.patch,
            context_request=response.context_request,
            message=response.message,
            usage=data["usage"],
            raw={
                **data,
                "events_path": str(events_path),
                "answer_path": str(answer_path),
                "prompt_path": str(prompt_path),
                "stderr_path": str(stderr_path),
            },
        )


def _terminate_process_tree(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _safe_tool_event(line: str) -> bool:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict) and _tool_event(value)


def shutil_which(program: str) -> str | None:
    """Local wrapper keeps the worker easy to monkeypatch in tests."""
    import shutil

    return shutil.which(program)


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["patch", "context_request", "final"]},
            "patch": {"type": "string"},
            "message": {"type": "string"},
            # Codex's strict output-schema mode requires every property to be
            # required.  Keeping request fields at the top level avoids an
            # optional nested object and keeps the protocol easy to recover.
            "paths": {"type": "array", "items": {"type": "string"}},
            "terms": {"type": "array", "items": {"type": "string"}},
            "max_lines": {"type": "integer", "minimum": 1, "maximum": 200},
            "reason": {"type": "string"},
        },
        "required": ["kind", "patch", "message", "paths", "terms", "max_lines", "reason"],
        "additionalProperties": False,
    }
