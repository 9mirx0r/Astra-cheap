#!/usr/bin/env python3
"""Astra-Ultra AST Tool for OpenAI Codex.

Generates code skeletons by eliding function, method, and generator bodies
with '...' (Ellipsis) or 'pass', preserving classes, signatures, decorators,
types, and docstrings. Supports Python and JS/TS.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

# Ensure stdout uses UTF-8 to prevent Windows charmap errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class PythonSkeletonTransformer(ast.NodeTransformer):
    """AST transformer that elides function, method, and generator bodies."""

    def __init__(self, style: str = 'ellipsis'):
        super().__init__()
        self.style = style

    def _create_placeholder(self) -> ast.AST:
        if self.style == 'pass':
            return ast.Pass()
        return ast.Expr(value=ast.Constant(value=Ellipsis))

    def _elide_function_body(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        docstring = ast.get_docstring(node, clean=False)
        new_body: List[ast.stmt] = []

        if docstring is not None and node.body:
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Expr) and isinstance(
                first_stmt.value, ast.Constant
            ):
                new_body.append(first_stmt)

        new_body.append(self._create_placeholder())
        node.body = new_body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._elide_function_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._elide_function_body(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        docstring = ast.get_docstring(node, clean=False)
        transformed_body: List[ast.stmt] = []

        for idx, stmt in enumerate(node.body):
            if (
                idx == 0
                and docstring is not None
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
            ):
                transformed_body.append(stmt)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                res = self.visit(stmt)
                if isinstance(res, list):
                    transformed_body.extend(res)
                elif res:
                    transformed_body.append(res)
            elif isinstance(stmt, (ast.AnnAssign, ast.Assign)):
                transformed_body.append(stmt)

        if not transformed_body:
            transformed_body.append(self._create_placeholder())

        node.body = transformed_body
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        if (
            isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == '__name__'
        ):
            node.body = [self._create_placeholder()]
            node.orelse = []
            return node
        return self.generic_visit(node)


def python_skeleton(code: str, style: str = 'ellipsis') -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f'# [Astra-Ultra AST SyntaxError: {exc}]\n' + code[:500]

    transformer = PythonSkeletonTransformer(style=style)
    skeleton_tree = transformer.visit(tree)
    ast.fix_missing_locations(skeleton_tree)
    return ast.unparse(skeleton_tree)


def python_symbols(code: str) -> List[dict[str, Any]]:
    symbols: List[dict[str, Any]] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return symbols

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({
                'name': node.name,
                'kind': 'function',
                'line': node.lineno,
                'col': node.col_offset,
                'doc': ast.get_docstring(node) or '',
            })
        elif isinstance(node, ast.ClassDef):
            symbols.append({
                'name': node.name,
                'kind': 'class',
                'line': node.lineno,
                'col': node.col_offset,
                'doc': ast.get_docstring(node) or '',
            })
    return symbols


JS_EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}


def is_js_ts_file(path: Path | str) -> bool:
    return Path(path).suffix.lower() in JS_EXTENSIONS


def js_ts_skeleton(code: str) -> str:
    lines = code.splitlines()
    output: List[str] = []
    in_function = False
    brace_depth = 0
    fn_regex = re.compile(
        r'^(?:export\s+)?(?:async\s+)?(?:function\*?\s+([a-zA-Z0-9_$]+)|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|(?:public|private|protected|static|async)*\s*([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{)'
    )
    class_regex = re.compile(
        r'^(?:export\s+)?(?:abstract\s+)?class\s+([a-zA-Z0-9_$]+)'
    )

    for line in lines:
        stripped = line.strip()
        if class_regex.search(stripped):
            output.append(line)
            continue

        if not in_function:
            match = fn_regex.search(stripped)
            if match and '{' in stripped:
                in_function = True
                brace_depth = line.count('{') - line.count('}')
                sig = line[: line.rfind('{') + 1]
                output.append(sig)
                indent = ' ' * (len(line) - len(line.lstrip()) + 2)
                output.append(f'{indent}...')
                if brace_depth <= 0:
                    output.append(line[line.rfind('}') :])
                    in_function = False
            else:
                if stripped.startswith(('import ', 'export ', 'type ', 'interface ')):
                    output.append(line)
        else:
            brace_depth += line.count('{') - line.count('}')
            if brace_depth <= 0:
                output.append(' ' * (len(line) - len(line.lstrip())) + '}')
                in_function = False

    return '\n'.join(output) if output else code[:1000]


def js_ts_symbols(code: str) -> List[dict[str, Any]]:
    symbols: List[dict[str, Any]] = []
    lines = code.splitlines()
    fn_regex = re.compile(
        r'(?:export\s+)?(?:async\s+)?(?:function\*?\s+([a-zA-Z0-9_$]+)|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)'
    )
    class_regex = re.compile(
        r'(?:export\s+)?(?:abstract\s+)?class\s+([a-zA-Z0-9_$]+)'
    )

    for idx, line in enumerate(lines, start=1):
        c_match = class_regex.search(line)
        if c_match:
            symbols.append({'name': c_match.group(1), 'kind': 'class', 'line': idx})
            continue
        f_match = fn_regex.search(line)
        if f_match:
            name = f_match.group(1) or f_match.group(2)
            symbols.append({'name': name, 'kind': 'function', 'line': idx})
    return symbols


def generate_skeleton(source_path: str | Path, style: str = 'ellipsis') -> str:
    path = Path(source_path)
    if not path.is_file():
        return f'# [Astra-Ultra AST: File not found: {source_path}]'

    try:
        content = path.read_text(encoding='utf-8-sig')
    except Exception as exc:
        return f'# [Astra-Ultra AST ReadError: {exc}]'

    if is_js_ts_file(path):
        return js_ts_skeleton(content)
    return python_skeleton(content, style=style)


def extract_symbols(source_path: str | Path) -> List[dict[str, Any]]:
    path = Path(source_path)
    if not path.is_file():
        return []

    try:
        content = path.read_text(encoding='utf-8-sig')
    except Exception:
        return []

    if is_js_ts_file(path):
        return js_ts_symbols(content)
    return python_symbols(content)


def main() -> int:
    parser = argparse.ArgumentParser(description='Astra-Ultra AST Tool for OpenAI Codex')
    subparsers = parser.add_subparsers(dest='command', required=True)

    skel_parser = subparsers.add_parser('skeleton', help='Generate code skeleton')
    skel_parser.add_argument('--source', required=True, help='Path to source file')
    skel_parser.add_argument('--style', choices=['ellipsis', 'pass'], default='ellipsis')

    sym_parser = subparsers.add_parser('symbols', help='Extract symbol table')
    sym_parser.add_argument('--source', required=True, help='Path to source file')

    args = parser.parse_args()

    if args.command == 'skeleton':
        print(generate_skeleton(args.source, style=args.style))
    elif args.command == 'symbols':
        syms = extract_symbols(args.source)
        print(json.dumps(syms, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
