"""Host-side verification and change metrics for real-task benchmark arms."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from real_task_catalog import RealTask


def _run(
    cmd: list[str],
    cwd: Path,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def git_text(cwd: Path, *args: str, timeout: int = 120) -> str:
    result = _run(["git", *args], cwd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr[-4000:]}")
    return result.stdout.strip()


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def run_command(
    cmd: list[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout: int,
) -> dict[str, Any]:
    """Run a host-side check and persist complete stdout/stderr evidence."""

    started = time.perf_counter()
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
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


def status_files(worktree: Path, base_sha: str) -> list[str]:
    names = git_text(worktree, "diff", base_sha, "--name-only").splitlines()
    status = _run(
        ["git", "status", "--porcelain=v1", "-z", "-uall"],
        worktree,
        timeout=120,
    )
    for line in status.stdout.split("\0"):
        if len(line) >= 3:
            name = line[3:].strip()
            if name and name not in names:
                names.append(name)
    return sorted(set(names))


def diff_stats(worktree: Path, base_sha: str, changed_files: list[str]) -> dict[str, Any]:
    numstat = git_text(worktree, "diff", base_sha, "--numstat").splitlines()
    added = 0
    deleted = 0
    for line in numstat:
        parts = line.split("\t")
        if len(parts) >= 2:
            added += int(parts[0]) if parts[0].isdigit() else 0
            deleted += int(parts[1]) if parts[1].isdigit() else 0
    tracked_names = set(git_text(worktree, "diff", base_sha, "--name-only").splitlines())
    for name in changed_files:
        if name not in tracked_names:
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
    task: RealTask,
) -> dict[str, Any]:
    """Run independent checks and derive the common completion verdict."""

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
    changed_files = status_files(worktree, base_sha)
    diff = diff_stats(worktree, base_sha, changed_files)
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
            "tests_touched": bool(diff["test_files_changed"]),
            "targeted_suite_green": test_result.get("returncode") == 0,
            "external_acceptance_green": acceptance_result.get("returncode") == 0,
            "codex_completed": result.get("agent_success", result.get("returncode") == 0),
            "no_whitespace_errors": diff["diff_check_passed"],
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
            "diff": diff,
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
