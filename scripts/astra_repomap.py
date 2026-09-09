#!/usr/bin/env python3
"""Astra-Ultra Personalized PageRank RepoMap for OpenAI Codex.

Generates a budget-fitted (<1,024 tokens) AST-driven repository map using
Personalized PageRank over symbol references. Designed specifically to fit
into OpenAI's 1,024-token prompt caching boundary.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXCLUDE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules", ".gemini",
    ".idea", ".vscode", "venv", ".venv", "env", "build", "dist",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".coverage"
}

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go",
    ".c", ".cpp", ".h", ".hpp", ".java", ".cs", ".rb"
}

REGEX_DEF = re.compile(
    r"^\s*(?:(?:pub|async|def|class|function|fn|struct|enum|interface|type)\s+)+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.MULTILINE
)
REGEX_IDENT = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + 3) // 4


def extract_python_symbols(filepath: Path, content: str) -> Tuple[List[Dict[str, Any]], Set[str]]:
    definitions: List[Dict[str, Any]] = []
    references: Set[str] = set()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return extract_regex_symbols(filepath, content)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append({
                "name": node.name,
                "kind": "function",
                "line": node.lineno,
                "file": str(filepath)
            })
        elif isinstance(node, ast.ClassDef):
            definitions.append({
                "name": node.name,
                "kind": "class",
                "line": node.lineno,
                "file": str(filepath)
            })
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            references.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            references.add(node.attr)

    return definitions, references


def extract_regex_symbols(filepath: Path, content: str) -> Tuple[List[Dict[str, Any]], Set[str]]:
    definitions: List[Dict[str, Any]] = []
    references: Set[str] = set()

    for idx, line in enumerate(content.splitlines(), start=1):
        m = REGEX_DEF.match(line)
        if m:
            definitions.append({
                "name": m.group(1),
                "kind": "symbol",
                "line": idx,
                "file": str(filepath)
            })

    for word in REGEX_IDENT.findall(content):
        references.add(word)

    return definitions, references


class RepoMapGraph:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.files: List[Path] = []
        self.definitions_by_file: Dict[str, List[Dict[str, Any]]] = {}
        self.references_by_file: Dict[str, Set[str]] = {}
        # Reused by the deterministic index so a worktree is not read twice.
        self.raw_contents: Dict[str, bytes] = {}
        self.all_symbols: Dict[str, List[str]] = {}
        self.adjacency: Dict[str, Set[str]] = {}

    def scan(self) -> None:
        self.files = []
        self.definitions_by_file = {}
        self.references_by_file = {}
        self.raw_contents = {}
        self.all_symbols = {}
        self.adjacency = {}
        for root, dirs, filenames in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in CODE_EXTENSIONS:
                    full_path = Path(root) / filename
                    self.files.append(full_path)

        self.files.sort(key=lambda path: path.as_posix())

        for filepath in self.files:
            rel_path = str(filepath.relative_to(self.root_dir)).replace("\\", "/")
            try:
                raw_content = filepath.read_bytes()
                content = raw_content.decode("utf-8-sig", errors="replace")
            except Exception:
                continue

            self.raw_contents[rel_path] = raw_content

            if filepath.suffix.lower() == ".py":
                defs, refs = extract_python_symbols(filepath, content)
            else:
                defs, refs = extract_regex_symbols(filepath, content)

            self.definitions_by_file[rel_path] = defs
            self.references_by_file[rel_path] = refs

            for d in defs:
                sym_name = d["name"]
                if sym_name not in self.all_symbols:
                    self.all_symbols[sym_name] = []
                self.all_symbols[sym_name].append(rel_path)

        for src_file, refs in self.references_by_file.items():
            self.adjacency[src_file] = set()
            for ref in refs:
                if ref in self.all_symbols:
                    for target_file in self.all_symbols[ref]:
                        if target_file != src_file:
                            self.adjacency[src_file].add(target_file)

    def calculate_pagerank(
        self,
        damping: float = 0.85,
        max_iter: int = 100,
        tol: float = 1e-6,
        focus_file: Optional[str] = None
    ) -> Dict[str, float]:
        nodes = list(self.definitions_by_file.keys())
        n = len(nodes)
        if n == 0:
            return {}

        node_indices = {node: idx for idx, node in enumerate(nodes)}
        pers = [1.0 / n] * n

        if focus_file:
            norm_focus = focus_file.replace("\\", "/")
            if norm_focus in node_indices:
                focus_idx = node_indices[norm_focus]
                pers = [0.0] * n
                pers[focus_idx] = 1.0

        scores = [1.0 / n] * n

        out_degrees = [len(self.adjacency.get(node, set())) for node in nodes]

        for _ in range(max_iter):
            next_scores = [(1.0 - damping) * pers[i] for i in range(n)]
            dangling_sum = sum(scores[i] for i in range(n) if out_degrees[i] == 0)

            for i in range(n):
                next_scores[i] += damping * dangling_sum * pers[i]

            for src_node, targets in self.adjacency.items():
                if src_node in node_indices:
                    src_idx = node_indices[src_node]
                    out_deg = out_degrees[src_idx]
                    if out_deg > 0:
                        share = (damping * scores[src_idx]) / out_deg
                        for target_node in targets:
                            if target_node in node_indices:
                                tgt_idx = node_indices[target_node]
                                next_scores[tgt_idx] += share

            err = sum(abs(next_scores[i] - scores[i]) for i in range(n))
            scores = next_scores
            if err < tol:
                break

        return {nodes[i]: scores[i] for i in range(n)}

    def render_map(
        self,
        budget_tokens: int = 1024,
        focus_file: Optional[str] = None
    ) -> str:
        ranks = self.calculate_pagerank(focus_file=focus_file)
        sorted_files = sorted(
            self.definitions_by_file.keys(),
            key=lambda f: ranks.get(f, 0.0),
            reverse=True
        )

        lines: List[str] = [
            "# Astra-Ultra RepoMap (PPR Optimized <= 1024 tokens)",
            f"# Root: {self.root_dir.name} | Total Files: {len(self.files)}"
        ]
        curr_tokens = estimate_tokens("\n".join(lines))

        for file_path in sorted_files:
            defs = self.definitions_by_file.get(file_path, [])
            if not defs:
                continue

            file_header = f"\n{file_path}:"
            file_tokens = estimate_tokens(file_header)
            if curr_tokens + file_tokens > budget_tokens - 20:
                lines.append("... [remaining symbols truncated for budget compliance]")
                break

            lines.append(file_header)
            curr_tokens += file_tokens

            for d in defs:
                kind_abbr = "c" if d["kind"] == "class" else "f"
                sym_line = f"  {kind_abbr} {d['name']} (L{d['line']})"
                sym_tokens = estimate_tokens(sym_line)
                if curr_tokens + sym_tokens > budget_tokens - 20:
                    lines.append("  ... [symbols truncated]")
                    return "\n".join(lines)
                lines.append(sym_line)
                curr_tokens += sym_tokens

        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Astra-Ultra Personalized PageRank RepoMap")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    map_p = subparsers.add_parser("map", help="Generate budget-fitted repository map")
    map_p.add_argument("--root", default=".", help="Root directory path")
    map_p.add_argument("--budget", type=int, default=1024, help="Token budget (default: 1024)")
    map_p.add_argument("--focus", default=None, help="Focus file to bias PageRank")

    sub_p = subparsers.add_parser("subgraph", help="Query symbol definitions and callers")
    sub_p.add_argument("--root", default=".", help="Root directory path")
    sub_p.add_argument("--symbol", required=True, help="Symbol name to query")

    args = parser.parse_args()
    root_dir = Path(args.root).resolve()
    graph = RepoMapGraph(root_dir)
    graph.scan()

    if args.subcommand == "map":
        print(graph.render_map(budget_tokens=args.budget, focus_file=args.focus))
    elif args.subcommand == "subgraph":
        defs = []
        for f, d_list in graph.definitions_by_file.items():
            for d in d_list:
                if d["name"] == args.symbol:
                    defs.append({"file": f, "line": d["line"], "kind": d["kind"]})

        callers = []
        for f, refs in graph.references_by_file.items():
            if args.symbol in refs:
                callers.append(f)

        res = {
            "symbol": args.symbol,
            "definitions": defs,
            "referencing_files": callers
        }
        print(json.dumps(res, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
