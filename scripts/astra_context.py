#!/usr/bin/env python3
"""Bounded progressive context selection for Astra-Ultra workers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

from astra_contracts import ContextPage, ContextRequest, TaskSpec
from astra_index import RepositoryIndex


def _estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4 if text else 0


@dataclass
class ContextBundle:
    """Pages currently visible to a worker, with no hidden source reads."""

    pages: List[ContextPage] = field(default_factory=list)

    @property
    def estimated_tokens(self) -> int:
        return sum(page.estimated_tokens for page in self.pages)

    @property
    def page_ids(self) -> tuple[str, ...]:
        return tuple(page.page_id for page in self.pages)

    def add(self, pages: Iterable[ContextPage], budget_tokens: int) -> List[ContextPage]:
        known = {page.page_id for page in self.pages}
        added: List[ContextPage] = []
        current = self.estimated_tokens
        for page in pages:
            if page.page_id in known:
                continue
            if current + page.estimated_tokens > budget_tokens:
                continue
            self.pages.append(page)
            known.add(page.page_id)
            added.append(page)
            current += page.estimated_tokens
        return added

    def render(self) -> str:
        chunks = []
        for page in self.pages:
            chunks.append(
                f"<context-page id={page.page_id!r} path={page.path!r} "
                f"lines={page.start_line}-{page.end_line} sha256={page.sha256!r}>\n"
                f"{page.text}\n</context-page>"
            )
        return "\n\n".join(chunks)


class ContextKernel:
    """Owns page construction, path confinement, and progressive disclosure."""

    def __init__(self, task: TaskSpec, index: RepositoryIndex):
        self.task = task
        self.index = index
        self.root = task.root

    def initial(self) -> ContextBundle:
        bundle = ContextBundle()
        map_budget = min(512, max(128, self.task.context_budget_tokens // 5))
        repo_map = self.index.repo_map(map_budget, self.task.focus_paths[0] if self.task.focus_paths else None)
        map_page = self._synthetic_page("__repo_map__", repo_map, "deterministic repository map")
        bundle.add([map_page], self.task.context_budget_tokens)

        ranked = self.index.ranked_paths(self.task.focus_terms, self.task.focus_paths)
        selected: List[str] = []
        # Initial context is deliberately shallow.  A worker can ask for a
        # missing page explicitly; loading every ranked file up front defeats
        # progressive disclosure and makes page-fault metrics meaningless.
        max_initial_files = max(1, min(2, self.task.context_budget_tokens // max(1, self.task.page_budget_tokens)))
        for path in (*self.task.focus_paths, *ranked):
            normalized = self.index.normalize_relative(path)
            if normalized not in selected:
                selected.append(normalized)
            if len(selected) >= max_initial_files:
                break

        for path in selected:
            pages = self._pages_for_path(
                path,
                self.task.focus_terms,
                self.task.page_budget_tokens,
                "initial ranked context",
            )[:2]
            if not bundle.add(pages, self.task.context_budget_tokens):
                break
        return bundle

    def resolve(self, request: ContextRequest, bundle: ContextBundle) -> List[ContextPage]:
        paths = list(request.paths)
        if not paths:
            paths = self.index.ranked_paths(request.terms or self.task.focus_terms, self.task.focus_paths)[:4]
        pages: List[ContextPage] = []
        missing: List[str] = []
        for path in paths[:6]:
            try:
                normalized = self._validate_path(path)
            except FileNotFoundError:
                missing.append(str(path))
                continue
            pages.extend(
                self._pages_for_path(
                    normalized,
                    request.terms or self.task.focus_terms,
                    min(self.task.page_budget_tokens, max(64, request.max_lines * 12)),
                    request.reason,
                    max_lines=request.max_lines,
                )
            )
        if missing:
            notice = self._synthetic_page(
                "__context_notice__",
                "Unavailable requested paths (they do not exist in this checkout):\n"
                + "\n".join(f"- {path}" for path in missing),
                "bounded missing-path notice",
            )
            pages.append(notice)
        return bundle.add(pages, self.task.context_budget_tokens)

    def _validate_path(self, path: str) -> str:
        normalized = self.index.normalize_relative(path)
        allowed = tuple(value.replace("\\", "/").strip("/") for value in self.task.allowed_paths)
        if allowed and not any(normalized == value or normalized.startswith(value.rstrip("/") + "/") for value in allowed):
            raise ValueError(f"context path is outside task allowlist: {normalized}")
        if normalized not in {record.path for record in self.index.records}:
            raise FileNotFoundError(normalized)
        return normalized

    def _synthetic_page(self, path: str, text: str, reason: str) -> ContextPage:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        page_id = hashlib.sha1(f"{path}:{digest}".encode("utf-8")).hexdigest()[:16]
        lines = max(1, len(text.splitlines()))
        return ContextPage(
            page_id=page_id,
            path=path,
            start_line=1,
            end_line=lines,
            text=text,
            sha256=digest,
            reason=reason,
            estimated_tokens=_estimate_tokens(text),
        )

    def _pages_for_path(
        self,
        path: str,
        terms: Sequence[str],
        budget_tokens: int,
        reason: str,
        max_lines: int | None = None,
    ) -> List[ContextPage]:
        text = self.index.read_text(path)
        lines = text.splitlines()
        if not lines:
            return [self._make_page(path, 1, 1, [""], reason, budget_tokens)]

        candidate_ranges: List[tuple[int, int]] = []
        generic_terms = {
            "class", "async", "def", "test", "tests", "output", "graph", "run", "result",
            "join", "state", "builder", "node", "path", "edge", "function", "list", "guidance",
        }
        search_terms: set[str] = set()
        for term in terms:
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(term)):
                if len(token) >= 6 and token.lower() not in generic_terms:
                    search_terms.add(token.lower())
        matches: list[tuple[int, int, str]] = []
        if search_terms:
            for index, line in enumerate(lines):
                lowered = line.lower()
                for token in search_terms:
                    if token in lowered:
                        matches.append((len(token), index, token))
        # Prefer long, specific identifiers over incidental prose matches, then
        # merge overlapping windows so one request stays bounded.
        radius = 10 if max_lines is None else min(80, max(10, max_lines // 2))
        for _, index, _ in sorted(matches, key=lambda item: (-item[0], item[1])):
            start = max(0, index - radius)
            end = min(len(lines), index + radius + 1)
            if any(start <= old_end and old_start <= end for old_start, old_end in candidate_ranges):
                continue
            candidate_ranges.append((start, end))
            if len(candidate_ranges) >= 6:
                break
        if not candidate_ranges:
            candidate_ranges.append((0, min(len(lines), max_lines or 40)))

        pages: List[ContextPage] = []
        for start, end in candidate_ranges:
            limit = max_lines or (end - start)
            end = min(end, start + max(1, limit))
            pages.append(self._make_page(path, start + 1, end, lines[start:end], reason, budget_tokens))
        return pages

    def _make_page(
        self,
        path: str,
        start_line: int,
        end_line: int,
        lines: Sequence[str],
        reason: str,
        budget_tokens: int,
    ) -> ContextPage:
        numbered = [f"{number}: {line}" for number, line in enumerate(lines, start=start_line)]
        text = "\n".join(numbered)
        if _estimate_tokens(text) > budget_tokens:
            max_chars = max(256, budget_tokens * 4)
            text = text[:max_chars].rstrip() + "\n[page truncated by token budget]"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        page_id = hashlib.sha1(f"{path}:{start_line}:{end_line}:{digest}".encode("utf-8")).hexdigest()[:16]
        return ContextPage(
            page_id=page_id,
            path=path,
            start_line=start_line,
            end_line=end_line,
            text=text,
            sha256=digest,
            reason=reason,
            estimated_tokens=_estimate_tokens(text),
        )
