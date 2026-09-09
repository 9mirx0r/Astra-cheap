#!/usr/bin/env python3
"""Safe patch lowering and bounded verification for detached worktrees."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from astra_contracts import TaskSpec
from astra_sanitizer import mask_observation


class PatchError(RuntimeError):
    """Raised when a worker patch is malformed or outside its grant."""


_DIFF_PATH = re.compile(r"^(?:---|\+\+\+)\s+(?:[ab]/)?(.+?)(?:\s+\t.*)?$")
_RANGED_HUNK = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@")


def _header_path(line: str) -> str | None:
    """Return a normalized path from a unified-diff file header."""
    raw = line[4:].split("\t", 1)[0].strip()
    if raw == "/dev/null":
        return None
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    return raw.replace("\\", "/")


def _expand_bare_hunks(lines: list[str], root: Path | None) -> list[str]:
    """Add line ranges to apply-patch-style ``@@`` hunks when possible."""
    if not any(line.startswith("@@") and not _RANGED_HUNK.match(line) for line in lines):
        return lines
    if root is None:
        raise PatchError("bare unified hunks require a workspace root")

    virtual: dict[str, list[str]] = {}
    old_path: str | None = None
    current_path: str | None = None

    def file_lines(relative: str) -> list[str]:
        if relative not in virtual:
            target = (root / relative).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError as exc:
                raise PatchError(f"patch path escapes workspace: {relative}") from exc
            if not target.is_file():
                raise PatchError(f"cannot expand hunk for missing file: {relative}")
            virtual[relative] = target.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        return virtual[relative]

    expanded: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("--- "):
            old_path = _header_path(line)
        elif line.startswith("+++ "):
            current_path = _header_path(line) or old_path
        if line.startswith("@@") and not _RANGED_HUNK.match(line):
            if not current_path:
                raise PatchError("bare hunk is missing a target file header")
            body: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor]
                if (
                    candidate.startswith("diff --git ")
                    or candidate.startswith("--- ")
                    or candidate.startswith("@@")
                ):
                    break
                if candidate != r"\ No newline at end of file":
                    body.append(candidate)
                cursor += 1
            source = file_lines(current_path)
            old_sequence = [entry[1:] if entry[:1] in {" ", "-", "+"} else entry for entry in body if entry[:1] != "+"]
            new_sequence = [entry[1:] if entry[:1] in {" ", "+"} else entry for entry in body if entry[:1] != "-"]
            try:
                start_index = next(
                    offset
                    for offset in range(len(source) - len(old_sequence) + 1)
                    if source[offset : offset + len(old_sequence)] == old_sequence
                )
            except StopIteration as exc:
                raise PatchError(f"could not locate bare hunk context in {current_path}") from exc
            start_line = start_index + 1
            old_count = len(old_sequence)
            new_count = len(new_sequence)
            suffix = line[2:].strip()
            expanded.append(
                f"@@ -{start_line},{old_count} +{start_line},{new_count} @@"
                + (f" {suffix}" if suffix else "")
            )
            expanded.extend(body)
            source[start_index : start_index + old_count] = new_sequence
            index = cursor
            continue
        expanded.append(line)
        index += 1
    return expanded


def _canonicalize_patch(patch_text: str, root: Path | None = None) -> str:
    """Accept common model diff variants while keeping Git as the parser.

    Codex workers occasionally emit a valid unified hunk with only ``---`` and
    ``+++`` headers.  Git's stdin parser is stricter when no ``diff --git``
    header is present, so add the metadata deterministically.  Markdown fences
    and the wrapper markers used by patch-oriented prompts are presentation,
    not patch content, and are removed before validation.
    """
    lines = patch_text.strip().splitlines()
    if not lines:
        return ""
    lines = [line for line in lines if line.strip() not in {"```", "```diff", "*** Begin Patch", "*** End Patch"}]
    has_git_header = any(line.startswith("diff --git ") for line in lines)

    normalized: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("*** Add File: "):
            relative = line.split(":", 1)[1].strip().replace("\\", "/")
            if not relative or relative == "/dev/null":
                raise PatchError("apply_patch add-file marker does not identify a file")
            content: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("*** "):
                entry = lines[index]
                if entry and not entry.startswith("+"):
                    raise PatchError(f"unsupported apply_patch add-file line for {relative}: {entry[:80]}")
                content.append(entry[1:] if entry.startswith("+") else "")
                index += 1
            normalized.extend(
                [
                    f"diff --git a/{relative} b/{relative}",
                    "new file mode 100644",
                    "--- /dev/null",
                    f"+++ b/{relative}",
                    f"@@ -0,0 +1,{len(content)} @@",
                    *(f"+{entry}" for entry in content),
                ]
            )
            continue
        if line.startswith("*** Update File: "):
            relative = line.split(":", 1)[1].strip().replace("\\", "/")
            if not relative or relative == "/dev/null":
                raise PatchError("apply_patch update-file marker does not identify a file")
            normalized.extend(
                [
                    f"diff --git a/{relative} b/{relative}",
                    f"--- a/{relative}",
                    f"+++ b/{relative}",
                ]
            )
            index += 1
            while index < len(lines) and not lines[index].startswith("*** "):
                normalized.append(lines[index])
                index += 1
            continue
        if line.startswith("*** Delete File: "):
            relative = line.split(":", 1)[1].strip().replace("\\", "/")
            if not relative or relative == "/dev/null":
                raise PatchError("apply_patch delete-file marker does not identify a file")
            if root is None:
                raise PatchError("apply_patch delete-file marker requires a workspace root")
            target = _safe_target(Path(root).resolve(), relative)
            if not target.is_file():
                raise PatchError(f"cannot delete missing file: {relative}")
            content = target.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            normalized.extend(
                [
                    f"diff --git a/{relative} b/{relative}",
                    "deleted file mode 100644",
                    f"--- a/{relative}",
                    "+++ /dev/null",
                    f"@@ -1,{len(content)} +0,0 @@",
                    *(f"-{entry}" for entry in content),
                ]
            )
            index += 1
            continue
        if line.startswith("*** "):
            raise PatchError("patch uses an unsupported apply_patch update/delete wrapper")
        if (
            not has_git_header
            and line.startswith("--- ")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("+++ ")
        ):
            old_path = _header_path(line)
            new_path = _header_path(lines[index + 1])
            display_old = old_path or new_path
            display_new = new_path or old_path
            if display_old is None or display_new is None:
                raise PatchError("unified diff headers do not identify a file")
            normalized.append(f"diff --git a/{display_old} b/{display_new}")
        normalized.append(line)
        index += 1
    normalized = _expand_bare_hunks(normalized, root)
    return "\n".join(normalized) + "\n"


@dataclass(frozen=True)
class ApplyResult:
    changed_paths: tuple[str, ...]
    patch_output: str


@dataclass(frozen=True)
class VerificationResult:
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


class WorkspaceTransaction:
    """Snapshot only the files a patch is allowed to touch."""

    def __init__(self, root: Path, paths: Iterable[str]):
        self.root = Path(root).resolve()
        self.paths = tuple(sorted(set(paths)))
        self._before: dict[str, bytes | None] = {}

    def snapshot(self) -> None:
        for relative in self.paths:
            target = _safe_target(self.root, relative)
            if target.exists() and not target.is_file():
                raise PatchError(f"transaction target is not a regular file: {relative}")
            self._before[relative] = target.read_bytes() if target.is_file() else None

    def rollback(self) -> None:
        for relative, data in self._before.items():
            target = _safe_target(self.root, relative)
            if data is None:
                if target.exists():
                    if target.is_file():
                        target.unlink()
                    else:
                        raise PatchError(f"cannot rollback non-file target: {relative}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def changed_paths(patch_text: str) -> tuple[str, ...]:
    if not patch_text.strip():
        raise PatchError("worker returned an empty patch")
    paths: set[str] = set()
    for line in patch_text.splitlines():
        match = _DIFF_PATH.match(line)
        if not match:
            continue
        raw = match.group(1).strip()
        if raw == "/dev/null":
            continue
        raw = raw.replace("\\", "/")
        if raw.startswith("/") or raw == ".." or raw.startswith("../") or "/../" in raw:
            raise PatchError(f"patch path escapes workspace: {raw}")
        paths.add(raw)
    if not paths:
        raise PatchError("patch contains no recognized file paths")
    return tuple(sorted(paths))


def _safe_target(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PatchError(f"patch path escapes workspace: {relative}") from exc
    return candidate


def _is_allowed(relative: str, allowed_paths: Sequence[str]) -> bool:
    if not allowed_paths:
        return True
    normalized = relative.replace("\\", "/").strip("/")
    return any(
        normalized == allowed.replace("\\", "/").strip("/")
        or normalized.startswith(allowed.replace("\\", "/").strip("/").rstrip("/") + "/")
        for allowed in allowed_paths
    )


def validate_patch_scope(root: Path, patch_text: str, task: TaskSpec) -> tuple[str, ...]:
    paths = changed_paths(_canonicalize_patch(patch_text, Path(root).resolve()))
    for relative in paths:
        _safe_target(root, relative)
        if not _is_allowed(relative, task.allowed_paths):
            raise PatchError(f"patch path is outside task allowlist: {relative}")
    return paths


def apply_patch(root: Path, patch_text: str, task: TaskSpec) -> ApplyResult:
    """Validate and apply a unified diff using git's parser, never a shell."""
    root = Path(root).resolve()
    canonical_patch = _canonicalize_patch(patch_text, root)
    paths = validate_patch_scope(root, canonical_patch, task)
    check = subprocess.run(
        ["git", "apply", "--check", "--recount", "--unidiff-zero", "--whitespace=nowarn", "-"],
        cwd=str(root),
        input=canonical_patch,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check.returncode != 0:
        raise PatchError(f"git apply --check failed: {(check.stderr or check.stdout).strip()[-3000:]}")
    applied = subprocess.run(
        ["git", "apply", "--recount", "--unidiff-zero", "--whitespace=nowarn", "-"],
        cwd=str(root),
        input=canonical_patch,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if applied.returncode != 0:
        raise PatchError(f"git apply failed: {(applied.stderr or applied.stdout).strip()[-3000:]}")
    return ApplyResult(changed_paths=paths, patch_output=(applied.stdout or applied.stderr).strip())


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
    return verify_command(task.root, task.test_command, task.verification_timeout_seconds)
