"""Bounded, deterministic source packets for real-task benchmark arms.

This module owns source selection and representation.  It deliberately does
not know how a benchmark is orchestrated or how an agent is executed; callers
provide the already-resolved base SHA so the packet remains a pure artifact of
the target checkout and task contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from real_task_catalog import RealTask


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _line_windows(
    path: Path,
    focuses: Iterable[str],
    *,
    context: int,
    max_windows: int = 8,
) -> list[dict[str, Any]]:
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
                    "lines": [
                        f"{number}: {lines[number - 1]}"
                        for number in range(start + 1, end + 1)
                    ],
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

        return python_skeleton(
            path.read_text(encoding="utf-8-sig", errors="replace")
        )[:12000]
    except Exception as exc:  # pragma: no cover - packet generation is fail-open
        return f"skeleton unavailable: {exc}"


def build_evidence_packet(
    target: Path,
    packet_path: Path,
    task: RealTask,
    base_sha: str,
) -> dict[str, Any]:
    """Build and persist a bounded source map without a model call."""

    target = target.resolve()
    files: list[dict[str, Any]] = []
    total_chars = 0
    for relative, focuses in task.evidence_files:
        path = (target / relative).resolve()
        if not path.is_file() or not path.is_relative_to(target):
            continue
        windows = _line_windows(
            path,
            focuses,
            context=6 if path.suffix == ".py" else 3,
        )
        skeleton = _skeleton(path)
        item = {
            "source": relative,
            "sha256": _sha256(path),
            "line_count": len(
                path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            ),
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
        "base_sha": base_sha,
        "files": files,
        "bounded_characters": total_chars,
    }
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return packet
