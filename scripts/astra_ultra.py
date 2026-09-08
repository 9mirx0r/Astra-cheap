#!/usr/bin/env python3
"""Astra-Ultra: Unified CLI for OpenAI Codex Token Optimization.

Provides single-command access to all Astra-Ultra optimization engines:
  - map: Personalized PageRank RepoMap (<=1024 tokens)
  - skeleton: AST skeleton extraction with elided function bodies
  - lock: Hardware-invariant prefix locking for OpenAI prompt caching
  - sanitize: Terminal noise suppression & test runner wrapping
  - govern: Reasoning effort governance for Luna 5.6 High, Terra, o1, o3-mini
  - mcp: Run FastMCP stdio symbol server
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent


def run_subscript(script_name: str, args: list[str]) -> int:
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="astra-ultra",
        description="Astra-Ultra: High-Precision Token Economizer for OpenAI Codex (Universal Model & Effort Support)"
    )
    subparsers = parser.add_subparsers(dest="tool", required=True)

    # RepoMap
    map_p = subparsers.add_parser("map", help="Generate budget-fitted Personalized PageRank RepoMap")
    map_p.add_argument("--root", default=".", help="Root directory")
    map_p.add_argument("--budget", type=int, default=1024, help="Token budget (default: 1024)")
    map_p.add_argument("--focus", default=None, help="Focus file")

    # AST Skeleton
    skel_p = subparsers.add_parser("skeleton", help="Generate code skeleton with elided bodies")
    skel_p.add_argument("--source", required=True, help="Path to source file")
    skel_p.add_argument("--style", choices=["ellipsis", "pass"], default="ellipsis")

    # Prefix Lock
    lock_p = subparsers.add_parser("lock", help="Build, verify, or quantize invariant prefix lock manifest")
    lock_p.add_argument("action", choices=["build", "verify", "quantize"])
    lock_p.add_argument("--root", default=".")
    lock_p.add_argument("--manifest", default="prefix_lock.json")
    lock_p.add_argument("--input", default=None, help="Input file for quantization")
    lock_p.add_argument("--out", default=None, help="Output file for quantization")
    lock_p.add_argument("--boundary", type=int, default=128, help="Token boundary increment (default: 128)")
    lock_p.add_argument("--min-tokens", type=int, default=1024, help="Minimum token threshold (default: 1024)")

    # MCP Server
    mcp_p = subparsers.add_parser("mcp", help="Run FastMCP stdio symbol server")
    mcp_p.add_argument("--test", action="store_true", help="Run self-test verification")

    # Governor
    gov_p = subparsers.add_parser("govern", help="Reasoning effort guidance and circuit breaker")
    gov_p.add_argument("--model", default="Luna-5.6", help="Model identifier")
    gov_p.add_argument("--effort", default="high", help="Effort setting: none, low, medium, high, max, xhigh")
    gov_p.add_argument("--asymmetric", action="store_true", help="Display formal Asymmetric 1-Turn Protocol")

    # Parse known args so trailing options pass through
    parsed, remaining = parser.parse_known_args()

    if parsed.tool == "map":
        cmd_args = ["map", "--root", parsed.root, "--budget", str(parsed.budget)]
        if parsed.focus:
            cmd_args.extend(["--focus", parsed.focus])
        return run_subscript("astra_repomap.py", cmd_args + remaining)

    elif parsed.tool == "skeleton":
        return run_subscript("astra_ast.py", ["skeleton", "--source", parsed.source, "--style", parsed.style] + remaining)

    elif parsed.tool == "lock":
        if parsed.action == "build":
            return run_subscript("astra_prefix_lock.py", ["build", "--root", parsed.root, "--out", parsed.manifest] + remaining)
        elif parsed.action == "verify":
            return run_subscript("astra_prefix_lock.py", ["verify", "--root", parsed.root, "--manifest", parsed.manifest] + remaining)
        elif parsed.action == "quantize":
            if not parsed.input:
                print("Error: --input is required for 'lock quantize'", file=sys.stderr)
                return 1
            cmd = ["quantize", "--input", parsed.input, "--boundary", str(parsed.boundary), "--min-tokens", str(parsed.min_tokens)]
            if parsed.out:
                cmd.extend(["--out", parsed.out])
            return run_subscript("astra_prefix_lock.py", cmd + remaining)

    elif parsed.tool == "mcp":
        mcp_args = ["--test"] if parsed.test else []
        return run_subscript("astra_mcp_server.py", mcp_args + remaining)

    elif parsed.tool == "govern":
        if parsed.asymmetric:
            return run_subscript("astra_governor.py", ["asymmetric"] + remaining)
        return run_subscript("astra_governor.py", ["guidance", "--model", parsed.model, "--effort", parsed.effort] + remaining)

    return 0


if __name__ == "__main__":
    sys.exit(main())
