#!/usr/bin/env python3
"""Bounded command verification for an Astra-Ultra task."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from astra_contracts import TaskSpec
from astra_sanitizer import mask_observation


@dataclass(frozen=True)
class VerificationResult:
    """The bounded, redacted evidence returned by one verification command."""

    passed: bool
    returncode: int | None
    elapsed_seconds: float
    stdout: str
    stderr: str
    command: tuple[str, ...]
    timed_out: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "returncode": self.returncode,
            "elapsed_seconds": self.elapsed_seconds,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "command": list(self.command),
            "timed_out": self.timed_out,
        }


def verify_command(root: Path, command: Sequence[str], timeout_seconds: int) -> VerificationResult:
    """Run only the task's explicit argv and return bounded evidence."""
    command = tuple(command)
    if not command:
        return VerificationResult(
            passed=False,
            returncode=None,
            elapsed_seconds=0.0,
            stdout="",
            stderr="verification command was not provided",
            command=(),
        )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(root),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.perf_counter() - started, 4)
        stdout = mask_observation(str(exc.stdout or ""), max_lines=25)
        stderr = mask_observation(str(exc.stderr or ""), max_lines=25)
        return VerificationResult(False, None, elapsed, stdout, stderr, command, timed_out=True)
    elapsed = round(time.perf_counter() - started, 4)
    return VerificationResult(
        passed=completed.returncode == 0,
        returncode=completed.returncode,
        elapsed_seconds=elapsed,
        stdout=mask_observation(completed.stdout, max_lines=25),
        stderr=mask_observation(completed.stderr, max_lines=25),
        command=command,
    )


def verify(task: TaskSpec) -> VerificationResult:
    """Verify a task using its declared primary test command."""
    return verify_command(task.root, task.test_command, task.verification_timeout_seconds)
