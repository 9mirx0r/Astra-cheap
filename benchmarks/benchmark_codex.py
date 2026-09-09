"""Baseline Codex provider adapter for the real-task benchmark harness."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from benchmark_support import calculate_cost, parse_codex_telemetry
from process_support import run_streaming_process


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
    log: Callable[[str], None],
) -> dict[str, Any]:
    """Run the plain Codex CLI and preserve its terminal telemetry."""

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
    # Stream JSONL directly to disk so progress and partial telemetry survive
    # watchdog termination.
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
        log=lambda message: log(f"[{variant}] {message}"),
    )
    stdout = events_path.read_text(encoding="utf-8", errors="replace")
    usage, response_text, observed = parse_codex_telemetry(stdout)
    answer_text = answer_path.read_text(encoding="utf-8", errors="replace") if answer_path.is_file() else ""
    usage_complete = bool(
        usage["input_tokens"]
        or usage["output_tokens"]
        or usage["cached_input_tokens"]
    )
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
        "returncode": None if process.timed_out else process.returncode,
        "agent_success": bool(not process.timed_out and process.returncode == 0),
        "elapsed_seconds": round(process.elapsed_seconds, 2),
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
    if process.timed_out:
        timeout_path.write_text(
            (
                f"Codex exceeded the {timeout}s timeout.\n"
                if not process.inactivity_timed_out
                else f"Codex produced no JSONL progress for {inactivity_timeout}s.\n"
            )
            + "Partial telemetry is preserved; zero tokens are not a billing estimate.\n",
            encoding="utf-8",
        )
        return {
            **common,
            "status": "inactivity_timeout" if process.inactivity_timed_out else "timeout",
            "usage_complete": False,
            "estimated_cost_usd": None,
            "usage_note": "No terminal telemetry before watchdog termination; zero is not a billing estimate.",
            "watchdog": "inactivity" if process.inactivity_timed_out else "wall_clock",
            "timeout_path": str(timeout_path.resolve()),
        }
    return {**common, "status": "completed" if process.returncode == 0 else "failed"}
