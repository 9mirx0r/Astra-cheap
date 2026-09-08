#!/usr/bin/env python3
"""Astra-Ultra FastMCP Symbol Server for OpenAI Codex (astra_mcp_server.py).

Implements Model Context Protocol (MCP) JSON-RPC 2.0 stdio transport.
Exposes surgical AST and symbol navigation tools with minimal schema tax:
  - get_repo_map: Budget-fitted Personalized PageRank symbol tree (<=1024 tokens).
  - get_symbol_subgraph: Definition locations and referencing callers for a symbol.
  - get_file_skeleton: AST elided signatures preserving types and docstrings.
  - get_bounded_slice: Focused log and source slices without whole-file dumping.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from astra_ast import generate_skeleton
from astra_repomap import RepoMapGraph

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "astra-symbol-server"
SERVER_VERSION = "1.0.0"

TOOLS_SCHEMA = [
    {
        "name": "get_repo_map",
        "description": "Returns a budget-fitted (<=1024 tokens) PageRank symbol map of the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root_dir": {
                    "type": "string",
                    "description": "Root directory path (defaults to current directory).",
                },
                "budget_tokens": {
                    "type": "integer",
                    "description": "Maximum token budget for the map (default: 1024).",
                },
                "focus_file": {
                    "type": "string",
                    "description": "Optional focus file to bias PageRank traversal.",
                },
            },
        },
    },
    {
        "name": "get_symbol_subgraph",
        "description": "Finds where a symbol is defined and lists all files that reference it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Identifier name (class, function, or method).",
                },
                "root_dir": {
                    "type": "string",
                    "description": "Root directory path (defaults to current directory).",
                },
            },
            "required": ["symbol_name"],
        },
    },
    {
        "name": "get_file_skeleton",
        "description": "Returns the AST skeleton of a file with function/method bodies elided.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file to skeletonize.",
                },
                "style": {
                    "type": "string",
                    "enum": ["ellipsis", "pass"],
                    "description": "Placeholder style for elided bodies (default: ellipsis).",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_bounded_slice",
        "description": "Extracts bounded line ranges from a file within an exact window.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to inspect.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "1-based starting line number (inclusive).",
                },
                "line_count": {
                    "type": "integer",
                    "description": "Number of lines to return (default: 50, max: 100).",
                },
            },
            "required": ["file_path"],
        },
    },
]


def handle_get_repo_map(args: Dict[str, Any]) -> Dict[str, Any]:
    root_str = args.get("root_dir", ".")
    budget = args.get("budget_tokens", 1024)
    focus = args.get("focus_file")

    root = Path(root_str).resolve()
    if not root.is_dir():
        return {"error": f"Directory not found: {root_str}"}

    graph = RepoMapGraph(root)
    graph.scan()
    repo_map = graph.render_map(budget_tokens=budget, focus_file=focus)
    return {"repo_map": repo_map}


def handle_get_symbol_subgraph(args: Dict[str, Any]) -> Dict[str, Any]:
    symbol = args.get("symbol_name")
    if not symbol:
        return {"error": "Missing required argument: symbol_name"}

    root_str = args.get("root_dir", ".")
    root = Path(root_str).resolve()
    if not root.is_dir():
        return {"error": f"Directory not found: {root_str}"}

    graph = RepoMapGraph(root)
    graph.scan()

    defs = []
    for f, d_list in graph.definitions_by_file.items():
        for d in d_list:
            if d["name"] == symbol:
                defs.append({"file": f, "line": d["line"], "kind": d["kind"]})

    callers = []
    for f, refs in graph.references_by_file.items():
        if symbol in refs:
            callers.append(f)

    return {
        "symbol": symbol,
        "definitions": defs,
        "referencing_files": callers,
    }


def handle_get_file_skeleton(args: Dict[str, Any]) -> Dict[str, Any]:
    file_path = args.get("file_path")
    if not file_path:
        return {"error": "Missing required argument: file_path"}

    style = args.get("style", "ellipsis")
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    skeleton = generate_skeleton(path, style=style)
    return {"file_path": file_path, "skeleton": skeleton}


def handle_get_bounded_slice(args: Dict[str, Any]) -> Dict[str, Any]:
    file_path = args.get("file_path")
    if not file_path:
        return {"error": "Missing required argument: file_path"}

    path = Path(file_path)
    if not path.is_file():
        return {"error": f"File not found: {file_path}"}

    start = max(1, args.get("start_line", 1))
    count = min(100, max(1, args.get("line_count", 50)))

    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except Exception as exc:
        return {"error": f"Failed to read file: {exc}"}

    total_lines = len(lines)
    end = min(total_lines, start + count - 1)
    slice_lines = lines[start - 1 : end]

    numbered = [f"{i}: {line}" for i, line in enumerate(slice_lines, start=start)]

    return {
        "file_path": file_path,
        "start_line": start,
        "end_line": end,
        "total_lines": total_lines,
        "content": "\n".join(numbered)
    }


def run_self_test() -> bool:
    print("Testing Astra-Ultra FastMCP Server...")
    test_file = Path(__file__).resolve()

    res1 = handle_get_file_skeleton({"file_path": str(test_file)})
    assert "skeleton" in res1, f"Failed skeleton: {res1}"

    res2 = handle_get_bounded_slice({"file_path": str(test_file), "start_line": 1, "line_count": 10})
    assert "content" in res2, f"Failed slice: {res2}"

    res3 = handle_get_repo_map({"root_dir": str(SCRIPT_DIR), "budget_tokens": 500})
    assert "repo_map" in res3, f"Failed repo_map: {res3}"

    print("All Astra-Ultra FastMCP server tools verified successfully!")
    return True


def process_mcp_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    msg_id = msg.get("id")
    method = msg.get("method")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS_SCHEMA},
        }

    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        handlers = {
            "get_repo_map": handle_get_repo_map,
            "get_symbol_subgraph": handle_get_symbol_subgraph,
            "get_file_skeleton": handle_get_file_skeleton,
            "get_bounded_slice": handle_get_bounded_slice,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

        try:
            result = handler(args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {str(exc)}"}],
                    "isError": True,
                },
            }

    if method == "notifications/initialized":
        return None

    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return None


def main() -> int:
    if "--test" in sys.argv:
        return 0 if run_self_test() else 1

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            resp = process_mcp_message(msg)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
