"""Run a fair, live three-arm benchmark on a real GitHub issue.

The benchmark deliberately keeps the agents in detached worktrees created from the
same upstream commit.  The host process, not either agent, runs the acceptance
checks and records the Codex JSONL telemetry.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
LATTICE_ROOT = ROOT / ".local" / "comparison-targets" / "lattice"
LATTICE_CLI = LATTICE_ROOT / "dist" / "cli.js"
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_support import calculate_cost, parse_codex_telemetry  # noqa: E402
from process_support import run_streaming_process  # noqa: E402
from real_task_catalog import RealTask, available_tasks  # noqa: E402
from astra_contracts import TaskSpec  # noqa: E402
from astra_runtime import AstraRuntime  # noqa: E402
from astra_worker import CodexExecWorker  # noqa: E402


_PRINT_LOCK = threading.Lock()


def _log(message: str) -> None:
    """Keep concurrent benchmark progress readable on one terminal."""
    with _PRINT_LOCK:
        print(message, flush=True)


REPO_URL = "https://github.com/pydantic/pydantic-ai.git"
ISSUE_URL = "https://github.com/pydantic/pydantic-ai/issues/4723"
ISSUE_TITLE = "New end_strategy='review' — let the model review and patch output before finalizing"
MODEL = "gpt-5.6-luna"
TASK_SLUG = "pydantic-ai-4723-review-output"
DEFAULT_TEST_COMMAND = [
    "uv",
    "run",
    "--frozen",
    "pytest",
    "tests/test_agent.py",
    "tests/test_agent_output_schemas.py",
    "-q",
    "--disable-warnings",
    "--maxfail=5",
    "-k",
    "not test_parallel_mcp_calls",
]


TASK_STATEMENT = f"""# Real GitHub task

- Repository: {REPO_URL}
- Issue: {ISSUE_URL}
- Title: {ISSUE_TITLE}

## Problem

Pydantic AI's output tool is terminal today: once `final_result` validates, the
run ends and the model cannot inspect or correct its own structured extraction.
This is a problem for forms, invoices and other extraction tasks where a schema
can validate while a field is still semantically wrong.

## Requested behavior

Add an opt-in `end_strategy='review'` mode.  When an output tool produces a
valid result, the framework should store it and return the serialized result to
the model as a non-terminal tool result.  The model must be able to either:

1. call an automatically generated JSON Patch RFC 6902 tool to apply a targeted
   patch to the stored result; the patched value must be revalidated and the
   updated value returned to the model; and
2. call a confirmation tool (the exact public name may follow project
   conventions) to finalize the validated current result.

Invalid output should retain the existing retry behavior. Existing strategies
(`early`, `graceful`, and `exhaustive`) must keep their behavior and the new
mode must remain opt-in and type-safe.

## Acceptance contract

- `Agent(..., end_strategy='review')` is accepted without changing the default.
- A valid output does not terminate the first model turn in review mode.
- A review-only flow can confirm a valid result and returns it to the caller.
- A patch flow can replace a nested scalar using an RFC 6902 operation, then
  confirm and return the patched, revalidated output.
- Invalid patches or invalid final output are rejected through the framework's
  existing retry/error path.
- Relevant tests and documentation are added, and the existing agent/output
  test suites remain green.

## Shared implementation plan

Use this order for both benchmark variants so the baseline is not forced to
rediscover the acceptance path from scratch:

1. Extend the public/type surface for the opt-in strategy while preserving all
   existing strategies.
2. Trace the final-output path through the agent graph and tool execution layer.
3. Implement the review state and generated confirmation/JSON-Patch tools at
   the narrowest existing output-tool seam.
4. Revalidate patched output through the existing output processor before
   returning it to the model.
5. Add focused confirm, patch, invalid-patch, regression, and documentation
   coverage; then run the targeted suite.

Prioritize a working vertical slice early. Do not spend the entire budget on
repository archaeology or broad refactoring.

Do not commit or push. Work only in the provided detached worktree.
"""


def _legacy_task() -> RealTask:
    """Keep the original review task available for report rechecks and reruns."""
    return RealTask(
        slug=TASK_SLUG,
        repository=REPO_URL,
        issue=ISSUE_URL,
        title=ISSUE_TITLE,
        target_directory="pydantic-ai",
        statement=TASK_STATEMENT,
        test_command=tuple(DEFAULT_TEST_COMMAND),
        evidence_files=EVIDENCE_FILES,
        acceptance_code="",
        required_surfaces=(
            (
                "review_strategy_surface",
                r"end_strategy.{0,100}review|review.{0,100}end_strategy",
            ),
            ("patch_surface", r"patch_result|json.?patch|JsonPatch"),
            ("confirmation_surface", r"confirm_result|confirmation"),
        ),
    )


def get_real_task(slug: str = TASK_SLUG) -> RealTask:
    """Resolve a task slug without allowing arbitrary code or paths from CLI input."""
    if slug == TASK_SLUG:
        return _legacy_task()
    task = available_tasks().get(slug)
    if task is None:
        available = ", ".join(sorted({TASK_SLUG, *available_tasks()}))
        raise ValueError(f"unknown real-task benchmark {slug!r}; choose one of: {available}")
    return task


EVIDENCE_FILES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AGENTS.md", ("Requirements of all contributions", "Development workflow", "Pydantic AI is meant")),
    ("pydantic_ai_slim/pydantic_ai/AGENTS.md", ("API Design", "Type System", "Testing")),
    ("tests/AGENTS.md", ("Testing", "Snapshot", "pytest")),
    (
        "pydantic_ai_slim/pydantic_ai/_agent_graph.py",
        ("EndStrategy", "def _handle_tool_calls", "def _handle_final_result", "process_tool_calls"),
    ),
    (
        "pydantic_ai_slim/pydantic_ai/_output.py",
        ("class OutputSchema", "class OutputToolset", "process_tool_call", "OutputToolset.for_run_step"),
    ),
    (
        "pydantic_ai_slim/pydantic_ai/output.py",
        ("class ToolOutput", "OutputContext", "OutputSpec"),
    ),
    (
        "pydantic_ai_slim/pydantic_ai/result.py",
        ("class FinalResult", "EndRun"),
    ),
    ("tests/test_agent.py", ("test_early_strategy", "test_graceful_strategy", "test_exhaustive_strategy")),
    ("tests/test_agent_output_schemas.py", ("output", "schema")),
    ("docs/agent.md", ("end_strategy", "output_type")),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(cmd: list[str], cwd: Path, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _git(cwd: Path, *args: str, timeout: int = 120) -> str:
    result = _run(["git", *args], cwd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr[-4000:]}")
    return result.stdout.strip()


def _line_windows(path: Path, focuses: Iterable[str], context: int = 7, max_windows: int = 8) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    windows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for focus in focuses:
        for index, line in enumerate(lines):
            if focus not in line:
                continue
            start = max(0, index - context)
            end = min(len(lines), index + context + 1)
            key = (start, end)
            if key in seen:
                continue
            seen.add(key)
            windows.append(
                {
                    "focus": focus,
                    "start_line": start + 1,
                    "end_line": end,
                    "lines": [f"{number}: {lines[number - 1]}" for number in range(start + 1, end + 1)],
                }
            )
            if len(windows) >= max_windows:
                return windows
    return windows


def _skeleton(path: Path) -> str:
    if path.suffix != ".py":
        return ""
    try:
        from astra_ast import python_skeleton

        return python_skeleton(path.read_text(encoding="utf-8-sig", errors="replace"))[:12000]
    except Exception as exc:  # pragma: no cover - packet generation must remain fail-open
        return f"skeleton unavailable: {exc}"


def build_evidence_packet(
    target: Path,
    packet_path: Path,
    task: RealTask | None = None,
) -> dict[str, Any]:
    """Build a bounded source map for Astra-Ultra without a model call."""
    task = task or get_real_task()
    files: list[dict[str, Any]] = []
    total_chars = 0
    for relative, focuses in task.evidence_files:
        path = (target / relative).resolve()
        if not path.is_file() or not path.is_relative_to(target.resolve()):
            continue
        windows = _line_windows(path, focuses, context=6 if path.suffix == ".py" else 3)
        skeleton = _skeleton(path)
        item = {
            "source": relative,
            "sha256": _sha256(path),
            "line_count": len(path.read_text(encoding="utf-8-sig", errors="replace").splitlines()),
            "skeleton": skeleton,
            "windows": windows,
            "authority": "untrusted_source_data",
        }
        encoded_size = len(json.dumps(item, ensure_ascii=False))
        if total_chars + encoded_size > 65000:
            item["skeleton"] = skeleton[:3000]
            item["windows"] = windows[:3]
            encoded_size = len(json.dumps(item, ensure_ascii=False))
        if total_chars + encoded_size <= 80000:
            files.append(item)
            total_chars += encoded_size

    packet = {
        "schema": 1,
        "kind": "real_task_evidence_packet",
        "authority": "untrusted_source_data",
        "repository": task.repository,
        "issue": task.issue,
        "base_sha": _git(target, "rev-parse", "HEAD"),
        "files": files,
        "bounded_characters": total_chars,
    }
    packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    return packet


def make_acceptance_harness(path: Path, task: RealTask | None = None) -> None:
    """Write black-box acceptance tests outside either agent worktree."""
    if task is not None and task.acceptance_code:
        path.write_text(task.acceptance_code, encoding="utf-8")
        return
    code = r'''from __future__ import annotations

import json
import sys

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


class Output(BaseModel):
    value: str


def _tools(info: AgentInfo):
    """Return output and generated function tools without duplicate names."""
    tools = []
    seen = set()
    for tool in [*(info.output_tools or []), *(info.function_tools or [])]:
        if tool.name not in seen:
            tools.append(tool)
            seen.add(tool.name)
    return tools


def _find_patch(info: AgentInfo):
    return next((tool for tool in _tools(info) if "patch" in tool.name.lower()), None)


def _is_confirmation_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in {"final_result", "output", "result"}:
        return False
    return any(marker in lowered for marker in ("confirm", "finalize", "review"))


def _find_confirmation(info: AgentInfo):
    return next((tool for tool in _tools(info) if _is_confirmation_name(tool.name)), None)


def _patch_args(tool):
    schema = tool.parameters_json_schema
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    key = next((key for key in props if any(word in key.lower() for word in ("patch", "operation", "ops"))), None)
    operation = {"op": "replace", "path": "/value", "value": "patched"}
    if key is None:
        return {"patches": [operation]}
    value_schema = props[key] if isinstance(props[key], dict) else {}
    if value_schema.get("type") == "array":
        return {key: [operation]}
    return {key: operation}


def run(mode: str) -> dict[str, object]:
    state = {"turn": 0}

    def model(messages, info: AgentInfo):
        turn = state["turn"]
        state["turn"] += 1
        if turn == 0:
            return ModelResponse(parts=[ToolCallPart("final_result", {"value": "initial"})])
        confirm = _find_confirmation(info)
        patch = _find_patch(info)
        if mode == "confirm":
            if confirm is None:
                raise AssertionError("review mode did not expose a confirmation tool")
            return ModelResponse(parts=[ToolCallPart(confirm.name, {})])
        if turn == 1:
            if patch is None:
                raise AssertionError("review mode did not expose a JSON patch tool")
            return ModelResponse(parts=[ToolCallPart(patch.name, _patch_args(patch))])
        if confirm is None:
            raise AssertionError("review mode did not expose a confirmation tool after patch")
        return ModelResponse(parts=[ToolCallPart(confirm.name, {})])

    agent = Agent(FunctionModel(model), output_type=Output, end_strategy="review")
    result = agent.run_sync("Extract the value and let me review it.")
    messages = result.all_messages()
    returns = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
    names = [part.tool_name.lower() for part in returns]
    expected = "initial" if mode == "confirm" else "patched"
    if result.output.value != expected:
        raise AssertionError(f"expected output {expected!r}, got {result.output.value!r}")
    if not any(name == "final_result" for name in names):
        raise AssertionError(f"final_result was not returned to the model: {names!r}")
    if not any(_is_confirmation_name(name) for name in names):
        raise AssertionError(f"confirmation was not recorded: {names!r}")
    if mode == "patch" and not any("patch" in name for name in names):
        raise AssertionError(f"patch was not recorded: {names!r}")
    return {"mode": mode, "output": result.output.model_dump(), "tool_return_names": names, "turns": state["turn"]}


if __name__ == "__main__":
    results = [run("confirm"), run("patch")]
    print(json.dumps({"accepted": True, "cases": results}))
'''
    path.write_text(code, encoding="utf-8")


def create_agent_report_schema(path: Path) -> Path:
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "changed_files": {"type": "array", "items": {"type": "string"}},
            "tests_added": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "changed_files", "tests_added", "risks"],
        "additionalProperties": False,
    }
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return path


def execute_agent(
    *,
    variant: str,
    prompt: str,
    worktree: Path,
    artifact_dir: Path,
    schema_path: Path,
    model: str,
    effort: str,
    timeout: int,
    inactivity_timeout: int,
) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    events_path = artifact_dir / f"{variant}.events.jsonl"
    stderr_path = artifact_dir / f"{variant}.stderr.txt"
    answer_path = artifact_dir / f"{variant}.answer.json"
    prompt_path = artifact_dir / f"{variant}.prompt.txt"
    timeout_path = artifact_dir / f"{variant}.timeout.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    cli = shutil.which("codex")
    if not cli:
        raise RuntimeError("codex executable not found on PATH")
    cmd = [
        cli,
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(worktree),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(answer_path),
        "--model",
        model.lower(),
        "-c",
        f"model_reasoning_effort={effort}",
        "-",
    ]
    # Stream JSONL directly to disk.  The shared process helper also enforces
    # the same watchdog semantics for the other provider adapters.
    process = run_streaming_process(
        cmd=cmd,
        cwd=worktree,
        stdin_path=prompt_path,
        stdout_path=events_path,
        stderr_path=stderr_path,
        activity_paths=(events_path,),
        activity_label="JSONL",
        heartbeat_formatter=lambda sizes: f"jsonl={sizes[0] / 1024:.0f}KiB",
        timeout=timeout,
        inactivity_timeout=inactivity_timeout,
        log=lambda message: _log(f"[{variant}] {message}"),
    )
    elapsed = process.elapsed_seconds
    timed_out = process.timed_out
    inactivity_timed_out = process.inactivity_timed_out
    returncode = process.returncode
    stdout = events_path.read_text(encoding="utf-8", errors="replace") if events_path.is_file() else ""
    usage, response_text, observed = parse_codex_telemetry(stdout)
    answer_text = answer_path.read_text(encoding="utf-8", errors="replace") if answer_path.is_file() else ""
    usage_complete = bool(usage["input_tokens"] or usage["output_tokens"] or usage["cached_input_tokens"])
    cost = (
        calculate_cost(
            model,
            usage["input_tokens"],
            usage["cached_input_tokens"],
            usage["output_tokens"],
            usage["cache_write_input_tokens"],
        )
        if usage_complete
        else None
    )
    common = {
        "variant": variant,
        "returncode": None if timed_out else returncode,
        "agent_success": bool(not timed_out and returncode == 0),
        "elapsed_seconds": round(elapsed, 2),
        "usage": usage,
        "usage_complete": usage_complete,
        "estimated_cost_usd": cost,
        "observed": observed,
        "response_preview": (answer_text or response_text)[-3000:],
        "worktree": str(worktree.resolve()),
        "events_path": str(events_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "answer_path": str(answer_path.resolve()),
        "prompt_path": str(prompt_path.resolve()),
        "command": cmd[:-1],
    }
    if timed_out:
        timeout_path.write_text(
            (
                f"Codex exceeded the {timeout}s timeout.\n"
                if not inactivity_timed_out
                else f"Codex produced no JSONL progress for {inactivity_timeout}s.\n"
            )
            + "Partial telemetry is preserved; zero tokens are not a billing estimate.\n",
            encoding="utf-8",
        )
        return {
            **common,
            "status": "inactivity_timeout" if inactivity_timed_out else "timeout",
            "usage_complete": False,
            "estimated_cost_usd": None,
            "usage_note": "No terminal telemetry before watchdog termination; zero is not a billing estimate.",
            "watchdog": "inactivity" if inactivity_timed_out else "wall_clock",
            "timeout_path": str(timeout_path.resolve()),
        }
    return {**common, "status": "completed" if returncode == 0 else "failed"}


def _runtime_focus_terms(task: RealTask) -> tuple[str, ...]:
    terms: list[str] = []
    generic = {
        "class",
        "async",
        "def",
        "tests",
        "test",
        "output",
        "graph",
        "join",
        "run",
        "result",
    }
    for _, focuses in task.evidence_files:
        for focus in focuses:
            phrase = focus.strip()
            if len(phrase) >= 6 and phrase not in terms:
                terms.append(phrase)
            for token in re.split(r"[^A-Za-z0-9_]+", focus):
                token = token.strip()
                if len(token) >= 6 and token.lower() not in generic and token not in terms:
                    terms.append(token)
    return tuple(terms[:32])


def execute_astra_runtime_agent(
    *,
    variant: str,
    task: RealTask,
    worktree: Path,
    artifact_dir: Path,
    acceptance_path: Path,
    model: str,
    effort: str,
    timeout: int,
    inactivity_timeout: int,
    test_timeout: int,
) -> dict[str, Any]:
    """Run Astra through its real context/patch/verification state machine.

    The provider receives read-only access and must return a canonical diff.
    The host runtime applies that diff and verifies the detached worktree, so a
    model cannot claim success merely by describing an edit in its final text.
    """
    runtime_dir = artifact_dir / f"{variant}.runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    result_path = artifact_dir / f"{variant}.runtime-result.json"
    evidence_paths = [relative for relative, _ in task.evidence_files]
    focus_paths = tuple(
        sorted(
            evidence_paths,
            key=lambda relative: (
                Path(relative).suffix.lower() not in {".py", ".ts", ".js", ".rs", ".go"},
                evidence_paths.index(relative),
            ),
        )
    )
    spec = TaskSpec(
        task_id=task.slug,
        objective=(
            task.statement
            + "\n\nEXTERNAL ACCEPTANCE ORACLE (must also pass):\n"
            + task.acceptance_code
        ),
        root=worktree,
        test_command=tuple(task.test_command),
        acceptance_command=(*task.verification_prefix, "python", str(acceptance_path)),
        focus_paths=focus_paths,
        focus_terms=_runtime_focus_terms(task),
        context_budget_tokens=task.astra_context_budget_tokens,
        page_budget_tokens=task.astra_page_budget_tokens,
        max_page_faults=task.astra_max_page_faults,
        max_turns=task.astra_max_turns,
        max_recoveries=task.astra_max_recoveries,
        verification_timeout_seconds=test_timeout,
    )
    worker = CodexExecWorker(
        model=model,
        effort=effort,
        timeout_seconds=timeout,
        inactivity_timeout_seconds=inactivity_timeout,
        artifact_dir=runtime_dir,
    )
    started = time.perf_counter()
    runtime_result = AstraRuntime(spec).run(worker)
    elapsed = round(time.perf_counter() - started, 2)
    result_path.write_text(json.dumps(runtime_result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    telemetry = dict(runtime_result.telemetry)
    usage = {
        "input_tokens": telemetry.get("input_tokens"),
        "cached_input_tokens": telemetry.get("cached_input_tokens"),
        "cache_write_input_tokens": None,
        "output_tokens": telemetry.get("output_tokens"),
        "reasoning_output_tokens": telemetry.get("reasoning_output_tokens"),
    }
    usage_complete = all(usage.get(key) is not None for key in ("input_tokens", "cached_input_tokens", "output_tokens"))
    cost = (
        calculate_cost(
            model,
            int(usage["input_tokens"]),
            int(usage["cached_input_tokens"]),
            int(usage["output_tokens"]),
            0,
        )
        if usage_complete
        else None
    )
    last_turn = max(1, int(telemetry.get("turns") or 1))
    runtime_dir_files = sorted(runtime_dir.glob(f"turn-{last_turn}.*"))
    prompt_path = next(
        (path for path in runtime_dir_files if path.suffix == ".txt" and "prompt" in path.name),
        runtime_dir / f"turn-{last_turn}.prompt.txt",
    )
    events_path = runtime_dir / f"turn-{last_turn}.events.jsonl"
    stderr_path = runtime_dir / f"turn-{last_turn}.stderr.txt"
    answer_path = runtime_dir / f"turn-{last_turn}.answer.json"
    provider_failed = runtime_result.status in {
        "worker_error",
        "runtime_error",
        "patch_failed",
        "verification_failed",
        "page_fault_limit",
        "context_budget_exhausted",
        "invalid_context_request",
        "turn_limit",
    }
    return {
        "variant": variant,
        "returncode": 1 if provider_failed else 0,
        "agent_success": not provider_failed,
        "status": "failed" if provider_failed else "completed",
        "runtime_status": runtime_result.status,
        "elapsed_seconds": elapsed,
        "usage": usage,
        "usage_complete": usage_complete,
        "estimated_cost_usd": cost,
        "observed": {
            "event_count": len(telemetry.get("events", [])),
            "turn_count": telemetry.get("turns", 0),
            "tool_call_count": telemetry.get("tool_call_count"),
            "observed_model": model,
            "observed_effort": effort,
        },
        "response_preview": runtime_result.message[-3000:],
        "worktree": str(worktree.resolve()),
        "evaluation_worktree": str(worktree.resolve()),
        "events_path": str(events_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "answer_path": str(answer_path.resolve()),
        "prompt_path": str(prompt_path.resolve()),
        "runtime_result_path": str(result_path.resolve()),
        "runtime_telemetry": telemetry,
        "command": ["astra-ultra", "run", "--worker", "codex", "--model", model, "--effort", effort],
    }


def _last_json_object(raw: str) -> dict[str, Any] | None:
    """Find the final JSON object emitted by Lattice's --json command."""
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def execute_lattice_agent(
    *,
    variant: str,
    goal: str,
    worktree: Path,
    artifact_dir: Path,
    model: str,
    effort: str,
    timeout: int,
    inactivity_timeout: int,
) -> dict[str, Any]:
    """Run the Lattice CLI and retain its verified transaction worktree.

    Lattice has its own runtime and therefore does not emit the Codex CLI JSONL
    stream used by the other two arms.  Its provider-reported counters and
    per-stage timings are preserved verbatim in a result artifact and mapped
    into the common benchmark shape below.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = artifact_dir / f"{variant}.stdout.txt"
    stderr_path = artifact_dir / f"{variant}.stderr.txt"
    prompt_path = artifact_dir / f"{variant}.prompt.txt"
    result_path = artifact_dir / f"{variant}.lattice-result.json"
    timeout_path = artifact_dir / f"{variant}.timeout.txt"
    prompt_path.write_text(goal, encoding="utf-8")

    node = shutil.which("node")
    if not node:
        raise RuntimeError("node executable not found on PATH")
    if not LATTICE_CLI.is_file():
        raise RuntimeError(f"Lattice CLI is not built: {LATTICE_CLI}")
    cmd = [
        node,
        str(LATTICE_CLI),
        "run",
        goal,
        "--worker",
        "codex",
        "--workspace",
        str(worktree),
        "--model",
        model.lower(),
        "--reasoning-effort",
        effort,
        "--json",
        "--retain-worktree",
        "--no-verified-cache",
    ]
    process = run_streaming_process(
        cmd=cmd,
        cwd=LATTICE_ROOT,
        stdin_path=None,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        activity_paths=(stdout_path, stderr_path),
        activity_label="Lattice stdout/stderr",
        heartbeat_formatter=lambda sizes: (
            f"stdout={sizes[0] / 1024:.0f}KiB stderr={sizes[1] / 1024:.0f}KiB"
        ),
        timeout=timeout,
        inactivity_timeout=inactivity_timeout,
        log=lambda message: _log(f"[{variant}] {message}"),
    )
    elapsed = process.elapsed_seconds
    timed_out = process.timed_out
    inactivity_timed_out = process.inactivity_timed_out
    returncode = process.returncode
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    lattice_result = _last_json_object(stdout)
    if lattice_result is not None:
        result_path.write_text(json.dumps(lattice_result, indent=2, ensure_ascii=False), encoding="utf-8")
    telemetry = lattice_result.get("telemetry", {}) if lattice_result else {}
    if not isinstance(telemetry, dict):
        telemetry = {}
    turns = telemetry.get("turnUsage") if isinstance(telemetry.get("turnUsage"), list) else []

    def counter(name: str, turn_name: str) -> int:
        value = telemetry.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return sum(
            int(turn.get(turn_name) or 0)
            for turn in turns
            if isinstance(turn, dict)
        )

    usage = {
        "input_tokens": counter("modelInputTokens", "inputTokens"),
        "cached_input_tokens": counter("cachedInputTokens", "cachedInputTokens"),
        "cache_write_input_tokens": 0,
        "output_tokens": counter("outputTokens", "outputTokens"),
        "reasoning_output_tokens": counter("reasoningTokens", "reasoningTokens"),
    }
    usage_complete = bool(
        usage["input_tokens"] or usage["cached_input_tokens"] or usage["output_tokens"]
    )
    provider_cost = telemetry.get("costUsd")
    cost = (
        float(provider_cost)
        if isinstance(provider_cost, (int, float)) and not isinstance(provider_cost, bool)
        else (
            calculate_cost(
                model,
                usage["input_tokens"],
                usage["cached_input_tokens"],
                usage["output_tokens"],
                usage["cache_write_input_tokens"],
            )
            if usage_complete
            else None
        )
    )
    transaction = lattice_result.get("transaction") if lattice_result else None
    evaluation_worktree = None
    if isinstance(transaction, dict) and transaction.get("worktree"):
        evaluation_worktree = str(Path(str(transaction["worktree"])).resolve())
    event_count = sum(1 for line in stderr.splitlines() if line.strip().startswith("{"))
    internal_status = lattice_result.get("status") if lattice_result else None
    agent_success = bool(
        not timed_out
        and returncode == 0
        and internal_status not in {"failed", "cancelled"}
    )
    common = {
        "variant": variant,
        "returncode": None if timed_out else returncode,
        "agent_success": agent_success,
        "status": "completed" if agent_success else ("timeout" if timed_out else "failed"),
        "internal_status": internal_status,
        "elapsed_seconds": round(elapsed, 2),
        "usage": usage,
        "usage_complete": usage_complete,
        "estimated_cost_usd": cost,
        "observed": {
            "event_count": event_count,
            "turn_count": telemetry.get("workerTurns", len(turns)),
            "tool_call_count": None,
            "observed_model": model,
            "observed_effort": effort,
        },
        "lattice_telemetry": telemetry,
        "response_preview": (
            (lattice_result.get("error") if isinstance(lattice_result, dict) else None)
            or (lattice_result.get("unifiedDiff", "") if isinstance(lattice_result, dict) else "")
        )[-3000:],
        "worktree": str(worktree.resolve()),
        "evaluation_worktree": evaluation_worktree or str(worktree.resolve()),
        "events_path": str(stderr_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "stdout_path": str(stdout_path.resolve()),
        "lattice_result_path": str(result_path.resolve()),
        "prompt_path": str(prompt_path.resolve()),
        "command": cmd,
    }
    if timed_out:
        timeout_path.write_text(
            (
                f"Lattice exceeded the {timeout}s timeout.\n"
                if not inactivity_timed_out
                else f"Lattice produced no stdout/stderr progress for {inactivity_timeout}s.\n"
            )
            + "Partial telemetry is preserved; zero tokens are not a billing estimate.\n",
            encoding="utf-8",
        )
        common.update(
            {
                "usage_complete": False,
                "estimated_cost_usd": None,
                "usage_note": "No terminal Lattice result before watchdog termination; zero is not a billing estimate.",
                "watchdog": "inactivity" if inactivity_timed_out else "wall_clock",
                "timeout_path": str(timeout_path.resolve()),
            }
        )
    return common


def run_command(
    cmd: list[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = _run(cmd, cwd, timeout=timeout)
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        return {
            "command": cmd,
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            "stdout_path": str(stdout_path.resolve()),
            "stderr_path": str(stderr_path.resolve()),
            "output_preview": (completed.stdout + "\n" + completed.stderr)[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = _decode(exc.stdout)
        stderr = _decode(exc.stderr)
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        return {
            "command": cmd,
            "returncode": None,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            "timeout": True,
            "stdout_path": str(stdout_path.resolve()),
            "stderr_path": str(stderr_path.resolve()),
            "output_preview": (stdout + "\n" + stderr)[-3000:],
        }


def _status_files(worktree: Path, base_sha: str) -> list[str]:
    names = _git(worktree, "diff", base_sha, "--name-only").splitlines()
    status = _run(["git", "status", "--porcelain=v1", "-z", "-uall"], worktree, timeout=120)
    for line in status.stdout.split("\0"):
        if len(line) >= 3:
            name = line[3:].strip()
            if name and name not in names:
                names.append(name)
    return sorted(set(names))


def _diff_stats(worktree: Path, base_sha: str, changed_files: list[str]) -> dict[str, Any]:
    numstat = _git(worktree, "diff", base_sha, "--numstat").splitlines()
    added = 0
    deleted = 0
    for line in numstat:
        parts = line.split("\t")
        if len(parts) >= 2:
            added += int(parts[0]) if parts[0].isdigit() else 0
            deleted += int(parts[1]) if parts[1].isdigit() else 0
    for name in changed_files:
        if not _git(worktree, "diff", base_sha, "--name-only").count(name):
            path = worktree / name
            if path.is_file():
                added += len(path.read_text(encoding="utf-8-sig", errors="replace").splitlines())
    check = _run(["git", "diff", base_sha, "--check"], worktree, timeout=120)
    normalized_changed = [name.replace("\\", "/") for name in changed_files]
    return {
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "test_files_changed": [
            name
            for name, normalized in zip(changed_files, normalized_changed)
            if normalized.startswith(("tests/", "testing/"))
            or "/tests/" in normalized
            or "/testing/" in normalized
            or Path(normalized).name.startswith("test_")
        ],
        "lines_added": added,
        "lines_deleted": deleted,
        "diff_check_passed": check.returncode == 0,
        "diff_check_output": check.stdout[-2000:] + check.stderr[-2000:],
    }


def evaluate_agent(
    *,
    variant: str,
    result: dict[str, Any],
    worktree: Path,
    base_sha: str,
    artifact_dir: Path,
    acceptance_path: Path,
    test_timeout: int,
    task: RealTask | None = None,
) -> dict[str, Any]:
    task = task or get_real_task()
    test_result = run_command(
        list(task.test_command),
        worktree,
        artifact_dir / f"{variant}.tests.stdout.txt",
        artifact_dir / f"{variant}.tests.stderr.txt",
        test_timeout,
    )
    acceptance_result = run_command(
        [*task.verification_prefix, "python", str(acceptance_path)],
        worktree,
        artifact_dir / f"{variant}.acceptance.stdout.txt",
        artifact_dir / f"{variant}.acceptance.stderr.txt",
        test_timeout,
    )
    changed_files = _status_files(worktree, base_sha)
    diff_stats = _diff_stats(worktree, base_sha, changed_files)
    source_text = ""
    for name in changed_files:
        path = worktree / name
        if path.suffix in {".py", ".md", ".toml"} and path.is_file():
            source_text += path.read_text(encoding="utf-8-sig", errors="replace") + "\n"
    criteria = {
        name: bool(re.search(pattern, source_text, re.I | re.S))
        for name, pattern in task.required_surfaces
    }
    criteria.update(
        {
            "tests_touched": bool(diff_stats["test_files_changed"]),
            "targeted_suite_green": test_result.get("returncode") == 0,
            "external_acceptance_green": acceptance_result.get("returncode") == 0,
            "codex_completed": result.get("agent_success", result.get("returncode") == 0),
            "no_whitespace_errors": diff_stats["diff_check_passed"],
        }
    )
    completion_criteria = {
        "codex_completed": criteria["codex_completed"],
        "tests_touched": criteria["tests_touched"],
        "targeted_suite_green": criteria["targeted_suite_green"],
        "external_acceptance_green": criteria["external_acceptance_green"],
        "no_whitespace_errors": criteria["no_whitespace_errors"],
    }
    functional_acceptance = criteria["external_acceptance_green"]
    completion = all(completion_criteria.values())
    failure_reasons: list[str] = []
    if not criteria["codex_completed"]:
        failure_reasons.append(f"agent_{result.get('status', 'failed')}")
    if not criteria["external_acceptance_green"]:
        failure_reasons.append("external_acceptance_failed")
    if not criteria["tests_touched"]:
        failure_reasons.append("no_tests_changed")
    if not criteria["targeted_suite_green"]:
        failure_reasons.append("targeted_suite_failed")
    if not criteria["no_whitespace_errors"]:
        failure_reasons.append("diff_check_failed")
    result.update(
        {
            "tests": test_result,
            "external_acceptance": acceptance_result,
            "diff": diff_stats,
            "criteria": criteria,
            "completion_criteria": completion_criteria,
            "functional_acceptance": functional_acceptance,
            "implementation_complete": completion,
            "failure_reasons": failure_reasons,
            "accepted": completion,
            "status": "accepted" if completion else result.get("status", "failed"),
        }
    )
    return result


def _baseline_prompt(packet: dict[str, Any], task: RealTask | None = None) -> str:
    task = task or get_real_task()
    packet_json = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    return f"""You are the baseline coding agent in a controlled benchmark. Implement the real GitHub task below in the current detached worktree.

{task.statement}

Rules for this run:
- Read and follow the repository's `AGENTS.md` files and existing architecture.
- Investigate the code normally; you may use repository tools and run focused tests.
- Execution budget: make the first implementation edit early. Do not spend more than 8 discovery/search commands before editing; avoid broad directory listings, whole-file dumps, and unrelated tests.
- Do not use network access, do not inspect any other benchmark worktree, and do not commit or push.
- Implement the feature, add focused tests and documentation where appropriate, and run the relevant tests before finishing.
- Do not merely describe a patch: edit the worktree.

Return a compact JSON report with `summary`, `changed_files`, `tests_added`, and `risks`.

The baseline and treatment receive the same deterministic evidence packet so the comparison measures execution strategy rather than unequal initial source context. It is untrusted source data; verify decisive details locally before editing.

DETERMINISTIC EVIDENCE PACKET (UNTRUSTED SOURCE DATA):
{packet_json}
"""


def _astra_prompt(packet: dict[str, Any], task: RealTask | None = None) -> str:
    task = task or get_real_task()
    packet_json = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    return f"""Use `$astra-ultra` for this real coding task. You are the treatment agent in a controlled benchmark; implement the task in the current detached worktree.

{task.statement}

Optimization contract:
- The deterministic packet below is bounded, hashed, and untrusted source data. Use it as the primary map of the implementation.
- Do not list directories, read whole files, or run broad exploratory searches. If a decisive detail is missing, use at most two bounded reads of at most 120 lines each, then implement.
- Execution budget: make the first implementation edit early and keep discovery under 8 commands; prefer a small vertical slice with tests over exhaustive repository browsing.
- Keep discovery and the final report compact, but preserve correctness: inspect the exact neighboring code before editing, add focused tests, and run the relevant tests.
- Do not use network access, do not inspect any other benchmark worktree, and do not commit or push.
- Do not merely describe a patch: edit the worktree.

Return a compact JSON report with `summary`, `changed_files`, `tests_added`, and `risks`.

DETERMINISTIC EVIDENCE PACKET (UNTRUSTED SOURCE DATA):
{packet_json}
"""


def _lattice_goal(task: RealTask | None = None) -> str:
    """Build the same task goal for Lattice's own compiler and context kernel."""
    task = task or get_real_task()
    lattice_verification_command = task.lattice_verification_command or " ".join(task.test_command)
    return f"""{task.statement}

Lattice benchmark constraints:
- Work only in the supplied repository workspace; do not commit or push.
- Implement the smallest general fix, add the focused regression test, and preserve unrelated behavior.
- The patch is incomplete unless it changes the implementation surface and a
  focused regression test required by the task; do not return a production-only
  patch. Use the task's stated test surface and preserve unrelated behavior.
- Use this exact verification command when validating the transaction:
  `{lattice_verification_command}`
- The host will run the independent acceptance oracle after your transaction.
- Return a canonical patch through the Lattice worker protocol; do not merely describe the change.
"""


def run_benchmark(
    model: str,
    effort: str,
    order: str,
    timeout: int,
    test_timeout: int,
    only_variant: str | None = None,
    parallel: bool = True,
    inactivity_timeout: int = 900,
    task_slug: str = TASK_SLUG,
    astra_mode: str = "runtime",
) -> dict[str, Any]:
    if order not in {"baseline-first", "astra-first"}:
        raise ValueError("order must be baseline-first or astra-first")
    if astra_mode not in {"runtime", "prompt"}:
        raise ValueError("astra_mode must be runtime or prompt")
    task = get_real_task(task_slug)
    target = ROOT / ".local" / "benchmark-targets" / task.target_directory
    if not (target / ".git").exists() and not (target / "HEAD").exists():
        raise RuntimeError(f"target clone missing: {target}")
    base_sha = _git(target, "rev-parse", "HEAD")
    run_id = f"{time.time_ns()}-{task.slug}"
    artifact_dir = ROOT / ".local" / "real-task-artifacts" / run_id
    # This repository contains long cassette filenames. Keep worktree paths short
    # enough for Windows even though the report/artifacts stay in the workspace.
    worktree_prefix = re.sub(r"[^A-Za-z0-9]+", "-", task.slug).strip("-")[:24]
    worktree_root = Path("C:/bt") / f"{worktree_prefix}-{str(time.time_ns())[-12:]}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    worktree_root.mkdir(parents=True, exist_ok=False)
    (artifact_dir / "task.md").write_text(task.statement, encoding="utf-8")
    (artifact_dir / "benchmark_config.json").write_text(
        json.dumps(
            {
                "task_slug": task.slug,
                "repository": task.repository,
                "issue": task.issue,
                "issue_title": task.title,
                "base_sha": base_sha,
                "model": model,
                "effort": effort,
                "order": order,
                "test_command": list(task.test_command),
                "verification_prefix": list(task.verification_prefix),
                "lattice_verification_command": task.lattice_verification_command,
                "timeout_seconds": timeout,
                "inactivity_timeout_seconds": inactivity_timeout,
                "test_timeout_seconds": test_timeout,
                "shared_evidence_packet": True,
                "astra_mode": astra_mode,
                "astra_context_budget_tokens": task.astra_context_budget_tokens,
                "astra_page_budget_tokens": task.astra_page_budget_tokens,
                "astra_max_page_faults": task.astra_max_page_faults,
                "astra_max_turns": task.astra_max_turns,
                "astra_max_recoveries": task.astra_max_recoveries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    packet = build_evidence_packet(target, artifact_dir / "evidence_packet.json", task)
    acceptance_path = artifact_dir / "acceptance_harness.py"
    make_acceptance_harness(acceptance_path, task)
    schema_path = create_agent_report_schema(artifact_dir / "agent_output.schema.json")

    variants = ["baseline", "astra-ultra", "lattice"]
    if order == "astra-first":
        variants.reverse()
    if only_variant is not None:
        variants = [only_variant]
    worktrees: dict[str, Path] = {}
    prompts = {
        "baseline": _baseline_prompt(packet, task),
        "astra-ultra": _astra_prompt(packet, task),
        "lattice": _lattice_goal(task),
    }
    results: dict[str, dict[str, Any]] = {}

    # Create both detached worktrees before starting either model. This makes
    # the comparison paired at the same base SHA and allows the model phase to
    # run concurrently instead of spending 2 x timeout_seconds wall-clock.
    for variant in variants:
        worktree = worktree_root / variant
        worktrees[variant] = worktree
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _log(f"[{variant}] creating detached worktree at {worktree}")
        added = _run(["git", "worktree", "add", "--detach", str(worktree), base_sha], target, timeout=180)
        if added.returncode != 0:
            raise RuntimeError(f"could not create {variant} worktree:\n{added.stderr[-4000:]}")

    def run_one(variant: str) -> tuple[str, dict[str, Any]]:
        _log(f"[{variant}] launching {model} at effort={effort}; timeout={timeout}s")
        if variant == "lattice":
            result = execute_lattice_agent(
                variant=variant,
                goal=prompts[variant],
                worktree=worktrees[variant],
                artifact_dir=artifact_dir,
                model=model,
                effort=effort,
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
            )
        elif variant == "astra-ultra" and astra_mode == "runtime":
            result = execute_astra_runtime_agent(
                variant=variant,
                task=task,
                worktree=worktrees[variant],
                artifact_dir=artifact_dir,
                acceptance_path=acceptance_path,
                model=model,
                effort=effort,
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
                test_timeout=test_timeout,
            )
        else:
            result = execute_agent(
                variant=variant,
                prompt=prompts[variant],
                worktree=worktrees[variant],
                artifact_dir=artifact_dir,
                schema_path=schema_path,
                model=model,
                effort=effort,
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
            )
        _log(f"[{variant}] Codex status={result.get('status')} elapsed={result.get('elapsed_seconds')}s")
        return variant, result

    agent_phase_started = time.perf_counter()
    if parallel and len(variants) > 1:
        _log(f"[runner] launching {len(variants)} agents in parallel")
        with ThreadPoolExecutor(max_workers=len(variants), thread_name_prefix="codex-agent") as pool:
            futures = [pool.submit(run_one, variant) for variant in variants]
            for future in as_completed(futures):
                variant, result = future.result()
                results[variant] = result
    else:
        _log("[runner] sequential mode")
        for variant in variants:
            name, result = run_one(variant)
            results[name] = result
    agent_phase_elapsed = time.perf_counter() - agent_phase_started

    def evaluate_one(variant: str) -> tuple[str, dict[str, Any]]:
        evaluation_worktree = Path(
            results[variant].get("evaluation_worktree", str(worktrees[variant]))
        )
        result = evaluate_agent(
            variant=variant,
            result=results[variant],
            worktree=evaluation_worktree,
            base_sha=base_sha,
            artifact_dir=artifact_dir,
            acceptance_path=acceptance_path,
            test_timeout=test_timeout,
            task=task,
        )
        _log(
            f"[{variant}] accepted={result['accepted']} tests={result['tests'].get('returncode')} "
            f"acceptance={result['external_acceptance'].get('returncode')} changed={result['diff']['changed_file_count']}"
        )
        return variant, result

    verification_started = time.perf_counter()
    if parallel and len(variants) > 1:
        _log(f"[runner] verifying {len(variants)} worktrees in parallel")
        with ThreadPoolExecutor(max_workers=len(variants), thread_name_prefix="benchmark-check") as pool:
            futures = [pool.submit(evaluate_one, variant) for variant in variants]
            for future in as_completed(futures):
                variant, result = future.result()
                results[variant] = result
    else:
        for variant in variants:
            name, result = evaluate_one(variant)
            results[name] = result
    verification_elapsed = time.perf_counter() - verification_started

    ordered_results = [
        results[variant]
        for variant in ("baseline", "astra-ultra", "lattice")
        if variant in results
    ]
    totals: dict[str, Any] = {}
    for result in ordered_results:
        usage = result.get("usage", {})
        totals[result["variant"]] = {
            **usage,
            "estimated_cost_usd": result.get("estimated_cost_usd"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "test_elapsed_seconds": result.get("tests", {}).get("elapsed_seconds"),
            "acceptance_elapsed_seconds": result.get("external_acceptance", {}).get("elapsed_seconds"),
            "event_count": result.get("observed", {}).get("event_count", 0),
            "turn_count": result.get("observed", {}).get("turn_count", 0),
            "tool_call_count": result.get("observed", {}).get("tool_call_count", 0),
            "accepted": result.get("accepted", False),
            "changed_file_count": result.get("diff", {}).get("changed_file_count", 0),
            "lines_added": result.get("diff", {}).get("lines_added", 0),
            "lines_deleted": result.get("diff", {}).get("lines_deleted", 0),
        }
    baseline = totals.get("baseline", {})
    ultra = totals.get("astra-ultra", {})

    def pct(base: Any, treatment: Any) -> float | None:
        if not isinstance(base, (int, float)) or not base:
            return None
        if not isinstance(treatment, (int, float)):
            return None
        return round((treatment - base) / base * 100, 2)

    def pair_metrics(treatment: dict[str, Any]) -> dict[str, Any]:
        return {
            "input_token_change_pct": pct(baseline.get("input_tokens"), treatment.get("input_tokens")),
            "cached_input_change_pct": pct(
                baseline.get("cached_input_tokens"), treatment.get("cached_input_tokens")
            ),
            "output_token_change_pct": pct(baseline.get("output_tokens"), treatment.get("output_tokens")),
            "reasoning_token_change_pct": pct(
                baseline.get("reasoning_output_tokens"), treatment.get("reasoning_output_tokens")
            ),
            "latency_change_pct": pct(baseline.get("elapsed_seconds"), treatment.get("elapsed_seconds")),
            "test_latency_change_pct": pct(
                baseline.get("test_elapsed_seconds"), treatment.get("test_elapsed_seconds")
            ),
            "cost_change_pct": pct(
                baseline.get("estimated_cost_usd"), treatment.get("estimated_cost_usd")
            ),
            "tool_call_change_pct": pct(
                baseline.get("tool_call_count"), treatment.get("tool_call_count")
            ),
            "speedup_factor": round(baseline["elapsed_seconds"] / treatment["elapsed_seconds"], 3)
            if baseline.get("elapsed_seconds") and treatment.get("elapsed_seconds")
            else None,
        }

    metrics = {
        "expected_variants": len(ordered_results),
        "input_token_change_pct": pct(baseline.get("input_tokens"), ultra.get("input_tokens")),
        "cached_input_change_pct": pct(baseline.get("cached_input_tokens"), ultra.get("cached_input_tokens")),
        "output_token_change_pct": pct(baseline.get("output_tokens"), ultra.get("output_tokens")),
        "reasoning_token_change_pct": pct(baseline.get("reasoning_output_tokens"), ultra.get("reasoning_output_tokens")),
        "latency_change_pct": pct(baseline.get("elapsed_seconds"), ultra.get("elapsed_seconds")),
        "test_latency_change_pct": pct(baseline.get("test_elapsed_seconds"), ultra.get("test_elapsed_seconds")),
        "cost_change_pct": pct(baseline.get("estimated_cost_usd"), ultra.get("estimated_cost_usd")),
        "tool_call_change_pct": pct(baseline.get("tool_call_count"), ultra.get("tool_call_count")),
        "speedup_factor": round(baseline["elapsed_seconds"] / ultra["elapsed_seconds"], 3)
        if baseline.get("elapsed_seconds") and ultra.get("elapsed_seconds")
        else None,
        "accepted_variants": sum(1 for result in ordered_results if result.get("accepted")),
        "functional_acceptance_variants": sum(
            1 for result in ordered_results if result.get("functional_acceptance")
        ),
        "completed_variants": sum(
            1 for result in ordered_results if result.get("implementation_complete")
        ),
        "comparison_vs_baseline": {
            "astra-ultra": pair_metrics(ultra),
            "lattice": pair_metrics(totals.get("lattice", {})),
        },
    }
    report = {
        "schema": 1,
        "benchmark": "real_github_task",
        "task_slug": task.slug,
        "repository": task.repository,
        "issue": task.issue,
        "issue_title": task.title,
        "base_sha": base_sha,
        "model": model,
        "effort": effort,
        "astra_mode": astra_mode,
        "order": order,
        "shared_evidence_packet": True,
        "execution_mode": "parallel" if parallel and len(variants) > 1 else "sequential",
        "agent_phase_elapsed_seconds": round(agent_phase_elapsed, 2),
        "verification_phase_elapsed_seconds": round(verification_elapsed, 2),
        "artifact_dir": str(artifact_dir.resolve()),
        "worktrees": {key: str(value.resolve()) for key, value in worktrees.items()},
        "results": ordered_results,
        "totals": totals,
        "metrics": metrics,
        "limitations": [
            "One issue and one live trial per variant; repeat with randomized order for a stronger estimate.",
            "Token and cost values are Codex telemetry; reasoning tokens are a subset of output tokens.",
            "Lattice is measured through its own runtime; its aggregate provider usage and stage timings are preserved in lattice_telemetry.",
            "The public Lattice v1.0.0 checkout needed a local benchmark adapter for Python/TOML indexing, uv verification, and max effort; the adapter diff is visible in the cloned comparison checkout.",
            "Functional acceptance and complete implementation are reported separately: a timeout can pass the black-box harness without being a finished contribution.",
            "The external acceptance harness tests the observable issue contract and does not replace maintainer review.",
        ],
    }
    result_path = artifact_dir / "real_task_results.json"
    result_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    default_name = (
        "results_real_pydantic_ai_4723.json"
        if task.slug == TASK_SLUG
        else f"results_real_{task.slug}.json"
    )
    default_result = ROOT / "benchmarks" / default_name
    default_result.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"REPORT={result_path.resolve()}")
    _log(f"COPY={default_result.resolve()}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        default=TASK_SLUG,
        choices=sorted({TASK_SLUG, *available_tasks()}),
        help="Real-task definition to benchmark.",
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default="max")
    parser.add_argument("--order", default="baseline-first", choices=["baseline-first", "astra-first"])
    parser.add_argument(
        "--only",
        choices=["baseline", "astra-ultra", "lattice"],
        help="Run only one variant; useful when resuming a valid prior run.",
    )
    parser.add_argument("--timeout", type=int, default=3600, help="Maximum wall-clock seconds per agent.")
    parser.add_argument("--inactivity-timeout", type=int, default=900, help="Terminate an agent after this many seconds without JSONL progress.")
    parser.add_argument("--test-timeout", type=int, default=900)
    parser.add_argument(
        "--astra-mode",
        default="runtime",
        choices=["runtime", "prompt"],
        help="Astra arm execution path: real patch/verification runtime or legacy prompt-only mode.",
    )
    parser.add_argument("--sequential", action="store_true", help="Disable parallel agent and verification phases.")
    args = parser.parse_args()
    report = run_benchmark(
        args.model,
        args.effort,
        args.order,
        args.timeout,
        args.test_timeout,
        args.only,
        parallel=not args.sequential,
        inactivity_timeout=args.inactivity_timeout,
        task_slug=args.task,
        astra_mode=args.astra_mode,
    )
    print(json.dumps(report["metrics"], indent=2))
    return 0 if report["metrics"]["accepted_variants"] == report["metrics"]["expected_variants"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
