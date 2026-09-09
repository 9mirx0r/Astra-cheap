#!/usr/bin/env python3
"""Deterministic repository inventory used by the context kernel.

This module owns discovery and fingerprints.  It deliberately does not decide
what the worker should edit; that decision belongs to ``astra_context``.
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from astra_ast import python_skeleton  # noqa: E402
from astra_repomap import CODE_EXTENSIONS, EXCLUDE_DIRS, RepoMapGraph, estimate_tokens  # noqa: E402


TEXT_EXTENSIONS = CODE_EXTENSIONS | {
    ".md", ".rst", ".txt", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml",
    ".sh", ".ps1", ".sql", ".lock", ".csv",
}


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    line_count: int
    byte_count: int
    symbols: Tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "line_count": self.line_count,
            "byte_count": self.byte_count,
            "symbols": list(self.symbols),
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_excluded(directory: str) -> bool:
    return directory in EXCLUDE_DIRS or directory.startswith(".")


class RepositoryIndex:
    """A stable file/symbol inventory with lazy source reads."""

    def __init__(self, root: Path, records: Sequence[FileRecord], graph: RepoMapGraph):
        self.root = root.resolve()
        self.records = tuple(sorted(records, key=lambda record: record.path))
        self.graph = graph
        self._by_path = {record.path: record for record in self.records}

    @classmethod
    def build(cls, root: Path, allowed_paths: Iterable[str] = ()) -> "RepositoryIndex":
        root = Path(root).resolve()
        if not root.is_dir():
            raise ValueError(f"repository root is not a directory: {root}")

        allowed = tuple(str(value).replace("\\", "/").strip("/") for value in allowed_paths if str(value).strip())
        graph = RepoMapGraph(root)
        graph.scan()
        graph.files = sorted(graph.files, key=lambda path: path.as_posix())

        records: List[FileRecord] = []

        def is_allowed(relative: str) -> bool:
            return not allowed or any(
                relative == item or relative.startswith(item.rstrip("/") + "/")
                for item in allowed
            )

        def add_record(relative: str, data: bytes, symbols: Tuple[str, ...] = ()) -> None:
            if not is_allowed(relative):
                return
            text = data.decode("utf-8-sig", errors="replace")
            records.append(
                FileRecord(
                    path=relative,
                    sha256=_sha256(data),
                    line_count=len(text.splitlines()),
                    byte_count=len(data),
                    symbols=symbols,
                )
            )

        # RepoMapGraph already read every code file. Reuse those bytes rather
        # than reading the largest part of a real repository a second time.
        for relative in sorted(graph.raw_contents):
            definitions = graph.definitions_by_file.get(relative, [])
            symbols = tuple(sorted({str(item["name"]) for item in definitions if item.get("name")}))
            add_record(relative, graph.raw_contents[relative], symbols)

        for current_root, directories, filenames in os.walk(root):
            directories[:] = sorted(directory for directory in directories if not _is_excluded(directory))
            for filename in sorted(filenames):
                path = (Path(current_root) / filename).resolve()
                relative = path.relative_to(root).as_posix()
                if path.suffix.lower() not in TEXT_EXTENSIONS or path.suffix.lower() in CODE_EXTENSIONS:
                    continue
                if not is_allowed(relative):
                    continue
                try:
                    data = path.read_bytes()
                except OSError:
                    continue
                add_record(relative, data)
        return cls(root, records, graph)

    def get(self, relative_path: str) -> FileRecord | None:
        return self._by_path.get(self.normalize_relative(relative_path))

    def normalize_relative(self, relative_path: str) -> str:
        candidate = Path(str(relative_path).replace("\\", "/"))
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.root / candidate).resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError(f"path escapes repository root: {relative_path}") from exc

    def read_text(self, relative_path: str) -> str:
        relative = self.normalize_relative(relative_path)
        record = self._by_path.get(relative)
        if record is None:
            raise FileNotFoundError(relative)
        return (self.root / relative).read_text(encoding="utf-8-sig", errors="replace")

    def repo_map(self, budget_tokens: int = 1024, focus_file: str | None = None) -> str:
        """Return the existing PageRank map through a deterministic public seam."""
        if budget_tokens <= 0:
            raise ValueError("budget_tokens must be positive")
        normalized_focus = None
        if focus_file:
            normalized_focus = self.normalize_relative(focus_file)
        return self.graph.render_map(budget_tokens=budget_tokens, focus_file=normalized_focus)

    def ranked_paths(self, terms: Iterable[str] = (), focus_paths: Iterable[str] = ()) -> List[str]:
        """Rank candidate files with cheap lexical evidence before body reads."""
        normalized_focus = {self.normalize_relative(path) for path in focus_paths}
        normalized_terms = tuple(term.lower() for term in terms if str(term).strip())
        scored: List[tuple[float, str]] = []
        for record in self.records:
            haystack = " ".join((record.path, *record.symbols)).lower()
            score = 0.0
            if record.path in normalized_focus:
                score += 1000.0
            for term in normalized_terms:
                if term in haystack:
                    score += 10.0
            if record.symbols:
                score += min(len(record.symbols), 8) * 0.01
            scored.append((score, record.path))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [path for _, path in scored]

    def skeleton(self, relative_path: str) -> str:
        relative = self.normalize_relative(relative_path)
        text = self.read_text(relative)
        if Path(relative).suffix.lower() == ".py":
            return python_skeleton(text)
        # Non-Python skeletonization remains intentionally conservative: a
        # signature-less body is less useful than a verbatim bounded window.
        return "\n".join(text.splitlines()[:80])

    def estimate_text_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def manifest(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "file_count": len(self.records),
            "files": [record.to_dict() for record in self.records],
        }
