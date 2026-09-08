"""Astra-Ultra Codex CLI Benchmark Runner.

Runs comparison trials between Baseline and Astra-Ultra on ANY model
(Luna 5.6, Terra, o1, o3-mini, GPT-4o) and ANY effort tier (low, medium, high, max).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from usage_ledger import record as record_usage


def main() -> int:
    parser = argparse.ArgumentParser(description="Astra-Ultra Benchmark Runner for Codex")
    parser.add_argument("--model", required=True, help="Model identifier (e.g. Luna-5.6, Terra, o3-mini)")
    parser.add_argument("--effort", default="high", choices=["none", "low", "medium", "high", "max", "xhigh"], help="Reasoning effort tier")
    parser.add_argument("--output", required=True, help="Path to write comparison JSON")
    parser.add_argument("--trials", type=int, default=1, help="Trials per variant")
    args = parser.parse_args()

    cli = shutil.which("codex")
    if not cli:
        print("Note: 'codex' CLI executable not found in PATH. Simulating benchmark harness check.")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    local = ROOT / ".local" / f"benchmark-{int(time.time())}"
    local.mkdir(parents=True, exist_ok=True)
    ledger_path = local / "usage.jsonl"

    lines = ["Export job started; schema expected: invoice-v4"]
    lines += [f"INFO stage=extract row={i:05d} scanned=ok" for i in range(4200)]
    lines += ["ERROR E_SCHEMA_MISMATCH record=INV-042 expected=invoice-v4 received=invoice-v3"]
    error_line = len(lines)
    lines += [f"INFO stage=cleanup item={i:05d} cleanup=ok" for i in range(800)]
    lines += ["INFO wrapper process completed successfully; export artifact was not written"]
    fixture = "\n".join(lines) + "\n"

    schema = {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "error_line": {"type": "integer"},
            "wrapper_success_proves_export": {"type": "boolean"},
            "next_check": {"type": "string"}
        },
        "required": ["root_cause", "error_line", "wrapper_success_proves_export", "next_check"],
        "additionalProperties": False
    }
    schema_path = local / "answer-schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    task = (
        "Diagnose the failed invoice export using logs/job.log in the current directory. "
        "Identify the actual cause with its exact 1-based log line, determine whether the final "
        "wrapper success proves export success, and give the next verification. "
        "Do not change source inputs or call a provider/network service. "
        "Return the required JSON."
    )

    results = []
    variants = ["baseline", "astra-ultra"]

    for variant in variants:
        work = local / variant
        (work / "logs").mkdir(parents=True, exist_ok=True)
        (work / "logs" / "job.log").write_text(fixture, encoding="utf-8")

        prompt = task
        if variant == "astra-ultra":
            prompt = f"Use $astra-ultra. Read instructions at {ROOT / 'SKILL.md'}.\n" + task

        answer = work / "answer.json"

        if cli:
            effort_arg = f'model_reasoning_effort="{args.effort}"'
            command = [
                cli, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                "--json", "--color", "never", "-m", args.model,
                "-c", effort_arg, "-s", "workspace-write",
                "-C", str(work), "--output-schema", str(schema_path),
                "-o", str(answer), "-"
            ]
            print(f"Starting {variant}: model={args.model}, effort={args.effort}", flush=True)
            start = time.monotonic()
            try:
                run = subprocess.run(
                    command, input=prompt, text=True, encoding="utf-8",
                    capture_output=True, timeout=300
                )
                elapsed = round(time.monotonic() - start, 2)
            except subprocess.TimeoutExpired:
                results.append({"variant": variant, "status": "timeout", "accepted": False})
                continue

            (work / "events.jsonl").write_text(run.stdout, encoding="utf-8")
            events = []
            for line in run.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            usage = [e.get("usage") for e in events if e.get("type") == "turn.completed" and e.get("usage")]
            ans_data = json.loads(answer.read_text(encoding="utf-8")) if answer.exists() and answer.stat().st_size else {}
            accepted = (
                run.returncode == 0
                and ans_data.get("error_line") == error_line
                and ans_data.get("wrapper_success_proves_export") is False
                and "schema" in ans_data.get("root_cause", "").lower()
            )
            results.append({
                "variant": variant,
                "returncode": run.returncode,
                "elapsed_seconds": elapsed,
                "usage": usage[-1] if usage else None,
                "accepted": accepted,
                "answer": ans_data,
                "status": "completed" if run.returncode == 0 else "failed"
            })
        else:
            print(f"CLI mode simulated for validation: {variant}")

    summary_data = {
        "model": args.model,
        "effort": args.effort,
        "task": "invoice_log_diagnosis",
        "expected_error_line": error_line,
        "results": results
    }

    output_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"Benchmark results recorded to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
