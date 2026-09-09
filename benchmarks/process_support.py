"""Shared subprocess lifecycle helpers for live benchmark providers.

The benchmark runner has several providers, but all of them need the same
operational guarantees: streamed artifacts, a wall-clock watchdog, an
inactivity watchdog, and process-tree cleanup.  Keeping that lifecycle here
prevents provider adapters from quietly drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import time
from typing import Callable, Iterable


@dataclass(frozen=True)
class StreamedProcessResult:
    """Outcome of a provider process monitored through output files."""

    returncode: int
    elapsed_seconds: float
    timed_out: bool
    inactivity_timed_out: bool


def terminate_process_tree(proc: subprocess.Popen[bytes], cwd: Path) -> None:
    """Stop a provider and its descendants without leaving children behind."""

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # The final proc.kill below is still useful when taskkill is
            # unavailable or races with a process that already exited.
            pass
    if proc.poll() is None:
        proc.kill()


def run_streaming_process(
    *,
    cmd: list[str],
    cwd: Path,
    stdin_path: Path | None,
    stdout_path: Path,
    stderr_path: Path,
    activity_paths: Iterable[Path],
    activity_label: str,
    heartbeat_formatter: Callable[[tuple[int, ...]], str],
    timeout: int,
    inactivity_timeout: int,
    log: Callable[[str], None],
) -> StreamedProcessResult:
    """Run a provider while persisting output and enforcing two watchdogs.

    ``activity_paths`` defines what counts as forward progress.  Codex only
    needs JSONL stdout, while Lattice considers both stdout and stderr active;
    the provider adapters express that policy without duplicating the loop.
    """

    activity_paths = tuple(activity_paths)
    started = time.perf_counter()
    timed_out = False
    inactivity_timed_out = False
    returncode: int | None = None

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdin_file = stdin_path.open("rb") if stdin_path is not None else None
    try:
        with (
            stdout_path.open("wb") as stdout_file,
            stderr_path.open("wb") as stderr_file,
        ):
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdin=stdin_file,
                stdout=stdout_file,
                stderr=stderr_file,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            next_heartbeat = started + 30
            last_activity = started
            last_sizes = tuple(0 for _ in activity_paths)
            while proc.poll() is None:
                now = time.perf_counter()
                sizes = tuple(
                    path.stat().st_size if path.exists() else 0
                    for path in activity_paths
                )
                if sizes != last_sizes:
                    last_sizes = sizes
                    last_activity = now
                if now >= started + timeout:
                    timed_out = True
                    log("process timeout reached; terminating process tree")
                    terminate_process_tree(proc, cwd)
                    break
                if now - last_activity >= inactivity_timeout:
                    timed_out = True
                    inactivity_timed_out = True
                    log(
                        f"no {activity_label} progress for {inactivity_timeout}s; "
                        "terminating process tree"
                    )
                    terminate_process_tree(proc, cwd)
                    break
                if now >= next_heartbeat:
                    log(
                        f"still running; elapsed={now - started:.0f}s "
                        f"{heartbeat_formatter(sizes)}"
                    )
                    next_heartbeat += 30
                time.sleep(1)
            try:
                returncode = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                returncode = proc.wait(timeout=30)
    finally:
        if stdin_file is not None:
            stdin_file.close()

    if returncode is None:
        raise RuntimeError("streamed process ended without a return code")
    return StreamedProcessResult(
        returncode=returncode,
        elapsed_seconds=time.perf_counter() - started,
        timed_out=timed_out,
        inactivity_timed_out=inactivity_timed_out,
    )
