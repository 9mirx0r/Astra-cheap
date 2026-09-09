"""Lattice provider adapter for the real-task benchmark harness."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from benchmark_support import calculate_cost
from process_support import run_streaming_process


def _last_json_object(raw: str) -> dict[str, Any] | None:
    """Find the final JSON object emitted by Lattice's ``--json`` command."""

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
    lattice_root: Path,
    log: Callable[[str], None],
) -> dict[str, Any]:
    """Run Lattice and map its native transaction telemetry to the common shape."""

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
    lattice_cli = lattice_root / "dist" / "cli.js"
    if not lattice_cli.is_file():
        raise RuntimeError(f"Lattice CLI is not built: {lattice_cli}")
    cmd = [
        node,
        str(lattice_cli),
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
        cwd=lattice_root,
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
        log=lambda message: log(f"[{variant}] {message}"),
    )
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    lattice_result = _last_json_object(stdout)
    if lattice_result is not None:
        result_path.write_text(
            json.dumps(lattice_result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
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
        not process.timed_out
        and process.returncode == 0
        and internal_status not in {"failed", "cancelled"}
    )
    common = {
        "variant": variant,
        "returncode": None if process.timed_out else process.returncode,
        "agent_success": agent_success,
        "status": "completed" if agent_success else ("timeout" if process.timed_out else "failed"),
        "internal_status": internal_status,
        "elapsed_seconds": round(process.elapsed_seconds, 2),
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
    if process.timed_out:
        timeout_path.write_text(
            (
                f"Lattice exceeded the {timeout}s timeout.\n"
                if not process.inactivity_timed_out
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
                "watchdog": "inactivity" if process.inactivity_timed_out else "wall_clock",
                "timeout_path": str(timeout_path.resolve()),
            }
        )
    return common
