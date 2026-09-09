"""Astra-Ultra runtime provider adapter for real-task benchmarks."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from astra_contracts import TaskSpec
from astra_runtime import AstraRuntime
from astra_worker import CodexExecWorker
from benchmark_support import calculate_cost
from real_task_catalog import RealTask


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
    """Run Astra's context/patch/verification state machine."""

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
    result_path.write_text(
        json.dumps(runtime_result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    telemetry = dict(runtime_result.telemetry)
    usage = {
        "input_tokens": telemetry.get("input_tokens"),
        "cached_input_tokens": telemetry.get("cached_input_tokens"),
        "cache_write_input_tokens": None,
        "output_tokens": telemetry.get("output_tokens"),
        "reasoning_output_tokens": telemetry.get("reasoning_output_tokens"),
    }
    usage_complete = all(
        usage.get(key) is not None
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    )
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
