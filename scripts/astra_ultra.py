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

    # Observable runtime
    run_p = subparsers.add_parser("run", help="Run one bounded task through the Astra runtime")
    run_p.add_argument("--root", default=".", help="Task workspace root")
    run_p.add_argument("--task-id", default="astra-task", help="Stable task identifier")
    run_p.add_argument("--objective", required=True, help="Task objective")
    run_p.add_argument("--test-command-json", default="[]", help="Verification argv as a JSON array")
    run_p.add_argument(
        "--acceptance-command-json",
        default="[]",
        help="Independent acceptance-oracle argv as a JSON array",
    )
    run_p.add_argument("--allowed-path", action="append", default=[], help="Allowed changed/context path (repeatable)")
    run_p.add_argument("--focus-path", action="append", default=[], help="Initial context focus path (repeatable)")
    run_p.add_argument("--focus-term", action="append", default=[], help="Initial context term (repeatable)")
    run_p.add_argument("--context-budget", type=int, default=4096)
    run_p.add_argument("--page-budget", type=int, default=1200)
    run_p.add_argument("--max-page-faults", type=int, default=4)
    run_p.add_argument("--max-turns", type=int, default=4)
    run_p.add_argument("--max-recoveries", type=int, default=2)
    run_p.add_argument("--verification-timeout", type=int, default=900)
    run_p.add_argument("--worker", choices=["scripted", "codex"], default="scripted")
    run_p.add_argument("--response-file", help="JSON array of scripted worker responses")
    run_p.add_argument("--patch-file", help="Shortcut for one scripted patch response")
    run_p.add_argument("--model", default="gpt-5.6-luna")
    run_p.add_argument("--effort", default="max")
    run_p.add_argument("--worker-timeout", type=int, default=900)
    run_p.add_argument("--output", help="Optional JSON result path")

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

    elif parsed.tool == "run":
        import json
        from astra_contracts import TaskSpec
        from astra_runtime import AstraRuntime
        from astra_worker import CodexExecWorker, ScriptedWorker

        def parse_argv_json(raw: str, flag: str) -> tuple[str, ...]:
            value = json.loads(raw)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"{flag} must be a JSON array containing only strings")
            return tuple(value)

        try:
            test_command = parse_argv_json(parsed.test_command_json, "--test-command-json")
            acceptance_command = parse_argv_json(parsed.acceptance_command_json, "--acceptance-command-json")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"Error: --test-command-json and --acceptance-command-json must be JSON arrays: {exc}",
                file=sys.stderr,
            )
            return 2
        task = TaskSpec(
            task_id=parsed.task_id,
            objective=parsed.objective,
            root=Path(parsed.root),
            test_command=test_command,
            acceptance_command=acceptance_command,
            allowed_paths=tuple(parsed.allowed_path),
            focus_paths=tuple(parsed.focus_path),
            focus_terms=tuple(parsed.focus_term),
            context_budget_tokens=parsed.context_budget,
            page_budget_tokens=parsed.page_budget,
            max_page_faults=parsed.max_page_faults,
            max_turns=parsed.max_turns,
            max_recoveries=parsed.max_recoveries,
            verification_timeout_seconds=parsed.verification_timeout,
        )
        if parsed.worker == "codex":
            worker = CodexExecWorker(parsed.model, parsed.effort, parsed.worker_timeout)
        else:
            responses = []
            if parsed.response_file:
                value = json.loads(Path(parsed.response_file).read_text(encoding="utf-8"))
                responses = value.get("responses", []) if isinstance(value, dict) else value
            elif parsed.patch_file:
                responses = [{
                    "kind": "patch",
                    "patch": Path(parsed.patch_file).read_text(encoding="utf-8"),
                }]
            worker = ScriptedWorker(responses)
        result = AstraRuntime(task).run(worker)
        payload = result.to_dict()
        output = json.dumps(payload, indent=2, ensure_ascii=False)
        if parsed.output:
            output_path = Path(parsed.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0 if result.accepted else 2

    elif parsed.tool == "govern":
        if parsed.asymmetric:
            return run_subscript("astra_governor.py", ["asymmetric"] + remaining)
        return run_subscript("astra_governor.py", ["guidance", "--model", parsed.model, "--effort", parsed.effort] + remaining)

    return 0


if __name__ == "__main__":
    sys.exit(main())
