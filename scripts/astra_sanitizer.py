#!/usr/bin/env python3
"""Astra-Ultra Terminal Noise Sanitizer & Observation Masker for OpenAI Codex.

Filters terminal output and intercepts 'run_command' / shell tool calls:
1. Pipeline Safety: Skips alteration when piped to machine utilities (xargs, wc, awk, jq).
2. Blocks 'cat' or 'type' over large files (>40 lines or >2KB).
3. Wraps test runners ('pytest', 'npm test', 'cargo test', 'go test') to save full
   logs to '.local/logs/test_output.log' and emit only the failure summary and tail.
4. Optimizes unpaged 'git log' by rewriting to '-n 15 --oneline'.
5. Observation Masking: Replaces historical verbose tool outputs with compact hashes.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

LARGE_FILE_BYTES_THRESHOLD = 2048
LARGE_FILE_LINES_THRESHOLD = 40

ANSI_ESCAPE_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

TEST_RUNNER_PATTERNS = [
    r"\bpytest\b",
    r"\bpython\s+(?:-m\s+)?(?:unittest|pytest)\b",
    r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b",
    r"\bnpx\s+(?:jest|vitest|mocha|pytest)\b",
    r"\b(?:vitest|jest|mocha)\b",
    r"\bcargo\s+test\b",
    r"\bgo\s+test\b",
    r"\b(?:mvn|gradle|gradlew)\s+test\b",
    r"\bdotnet\s+test\b",
]
TEST_RUNNER_REGEX = re.compile("|".join(TEST_RUNNER_PATTERNS), re.IGNORECASE)

CAT_TYPE_REGEX = re.compile(
    r"(?:^|[;&|]\s*)(?:cat|type|Get-Content|gc)\s+([^\s|><;&]+|\"[^\"]+\"|'[^']+')",
    re.IGNORECASE,
)

PAGING_PIPES_REGEX = re.compile(
    r"\|\s*(?:head|tail|more|less|Select-Object\s+-(?:First|Last)|select\s+-(?:first|last)|sls|grep|findstr)\b",
    re.IGNORECASE,
)

MACHINE_PIPE_REGEX = re.compile(
    r"\|\s*(?:xargs|wc|awk|cut|sort|uniq|jq|column)\b",
    re.IGNORECASE,
)

GIT_LOG_REGEX = re.compile(r"\bgit\s+log\b", re.IGNORECASE)
GIT_LOG_PAGED_REGEX = re.compile(
    r"(?:-n\s*\d+|-\d+\b|--max-count(?:=|\s+)\d+)",
    re.IGNORECASE,
)


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_REGEX.sub("", text)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + 3) // 4


def mask_observation(text: str, max_lines: int = 25) -> str:
    """JetBrains observation masking: collapses verbose outputs while preserving signals."""
    if not text:
        return ""
    clean = strip_ansi(text)
    lines = clean.splitlines()
    if len(lines) <= max_lines:
        return clean

    head = lines[:5]
    tail = lines[-15:]
    omitted = len(lines) - len(head) - len(tail)
    return (
        "\n".join(head)
        + f"\n\n[... {omitted} lines of verbose output masked for context economy ...]\n\n"
        + "\n".join(tail)
    )


def is_large_file(file_path: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    clean_path = file_path.strip("\"'")
    candidates = [clean_path]
    if cwd and not os.path.isabs(clean_path):
        candidates.append(os.path.join(cwd, clean_path))

    target = None
    for c in candidates:
        if os.path.isfile(c):
            target = c
            break

    if target:
        try:
            sz = os.path.getsize(target)
            if sz > LARGE_FILE_BYTES_THRESHOLD:
                return True, f"{sz} bytes (threshold: {LARGE_FILE_BYTES_THRESHOLD} B)"
            with open(target, "r", encoding="utf-8-sig", errors="replace") as f:
                lc = sum(1 for _ in f)
                if lc > LARGE_FILE_LINES_THRESHOLD:
                    return True, f"{lc} lines (threshold: {LARGE_FILE_LINES_THRESHOLD} lines)"
        except Exception:
            pass

    ext = os.path.splitext(clean_path)[1].lower()
    code_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".log", ".txt", ".md"}
    if ext in code_exts and not target:
        return True, "unbounded source or log file"

    return False, ""


def process_command(cmd_line: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    if not cmd_line or not cmd_line.strip():
        return {"decision": "allow"}

    stripped = cmd_line.strip()

    # 0. Preserve machine pipelines
    if MACHINE_PIPE_REGEX.search(stripped):
        return {
            "decision": "allow",
            "reason": "Machine pipeline detected (| xargs/wc/awk/jq): raw stream preserved."
        }

    # 1. Prohibit cat / type on large files
    cat_match = CAT_TYPE_REGEX.search(stripped)
    if cat_match:
        if not PAGING_PIPES_REGEX.search(stripped):
            arg = cat_match.group(1).strip()
            if not arg.startswith("-") and not arg.startswith("/"):
                large, detail = is_large_file(arg, cwd)
                if large:
                    return {
                        "decision": "deny",
                        "reason": (
                            f"Command denied by Astra-Ultra token discipline: "
                            f"Direct dump via 'cat/type' detected on '{arg}' ({detail}). "
                            f"To preserve context and tokens, use 'view_file' with line bounds."
                        )
                    }

    # 2. Test runners
    if "test_output.log" not in stripped and TEST_RUNNER_REGEX.search(stripped):
        log_dir = ".local/logs"
        log_file = ".local/logs/test_output.log"
        tail_lines = 30

        if sys.platform == "win32":
            wrapped = (
                f"if (!(Test-Path -Path '{log_dir}')) {{ "
                f"New-Item -ItemType Directory -Force -Path '{log_dir}' | Out-Null }}; "
                f"& {{ {stripped} }} *>&1 | "
                f"Out-File -FilePath '{log_file}' -Encoding utf8; "
                f"Get-Content '{log_file}' -Tail {tail_lines}; "
                f"Write-Output '[full output saved to: {log_file}]'"
            )
        else:
            wrapped = (
                f"mkdir -p '{log_dir}' && "
                f"{{ {stripped} ; }} > '{log_file}' 2>&1 ; "
                f"tail -n {tail_lines} '{log_file}' ; "
                f"echo '[full output saved to: {log_file}]'"
            )

        return {
            "decision": "allow",
            "reason": "Test runner detected: stdout wrapped to bounded tail with local log tee.",
            "overwrite": {"CommandLine": wrapped}
        }

    # 3. Unbounded git log
    if GIT_LOG_REGEX.search(stripped) and not GIT_LOG_PAGED_REGEX.search(stripped):
        if not PAGING_PIPES_REGEX.search(stripped):
            optimized = GIT_LOG_REGEX.sub("git log -n 15 --oneline", stripped, count=1)
            return {
                "decision": "allow",
                "reason": "Unbounded 'git log' optimized with '-n 15 --oneline'.",
                "overwrite": {"CommandLine": optimized}
            }

    return {"decision": "allow"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Astra-Ultra Terminal Sanitizer & Masker")
    parser.add_argument("--eval-cmd", help="Evaluate a single command string")
    parser.add_argument("--mask-file", help="Apply observation masking to a file")

    args = parser.parse_args()

    if args.eval_cmd:
        res = process_command(args.eval_cmd)
        print(json.dumps(res, indent=2))
        return 0

    if args.mask_file:
        p = Path(args.mask_file)
        if p.is_file():
            content = p.read_text(encoding="utf-8-sig", errors="replace")
            print(mask_observation(content))
        return 0

    # STDIN/STDOUT Hook Mode
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return 0
        payload = json.loads(raw_input)
        cmd = payload.get("toolCall", {}).get("args", {}).get("CommandLine", "")
        cwd = payload.get("toolCall", {}).get("args", {}).get("Cwd", os.getcwd())
        decision = process_command(cmd, cwd)
        print(json.dumps(decision, indent=2))
    except Exception as exc:
        print(json.dumps({"decision": "allow", "error": str(exc)}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
