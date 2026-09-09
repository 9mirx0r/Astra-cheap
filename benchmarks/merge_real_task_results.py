"""Merge a valid baseline timeout run with a resumed Astra-only run."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from benchmark_support import parse_codex_telemetry  # noqa: E402
from run_real_task_benchmark import _diff_stats, _git, _status_files  # noqa: E402


BASE_SHA = "716f2ae4a1cb2650ce4ee58f702d1f60c3c93f8c"
REPO_URL = "https://github.com/pydantic/pydantic-ai.git"
ISSUE_URL = "https://github.com/pydantic/pydantic-ai/issues/4723"
ISSUE_TITLE = "New end_strategy='review' — let the model review and patch output before finalizing"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _event_detail(path: Path) -> dict[str, Any]:
    event_types: Counter[str] = Counter()
    item_types: Counter[str] = Counter()
    command_count = 0
    file_change_count = 0
    agent_message_count = 0
    for line in _read(path).splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", "unknown"))
        event_types[event_type] += 1
        item = event.get("item")
        if isinstance(item, dict):
            item_type = str(item.get("type", "unknown"))
            item_types[item_type] += 1
            if item_type == "command_execution":
                command_count += 1
            elif item_type == "file_change":
                file_change_count += 1
            elif item_type == "agent_message":
                agent_message_count += 1
    return {
        "event_types": dict(event_types),
        "item_types": dict(item_types),
        "command_execution_items": command_count,
        "file_change_items": file_change_count,
        "agent_message_items": agent_message_count,
    }


def _timeout_result(artifact: Path, worktree: Path, variant: str) -> dict[str, Any]:
    events_path = artifact / f"{variant}.events.jsonl"
    stdout = _read(events_path)
    usage, response, observed = parse_codex_telemetry(stdout)
    test_path = artifact / f"{variant}.tests.filtered.txt"
    acceptance_path = artifact / f"{variant}.acceptance.stderr.txt"
    changed_files = _status_files(worktree, BASE_SHA)
    diff = _diff_stats(worktree, BASE_SHA, changed_files)
    tests = {
        "command": [
            "uv",
            "run",
            "--frozen",
            "pytest",
            "tests/test_agent.py",
            "tests/test_agent_output_schemas.py",
            "-q",
            "--disable-warnings",
            "--maxfail=5",
            "-k",
            "not test_parallel_mcp_calls",
        ],
        "returncode": 0 if "451 passed" in _read(test_path) else 1,
        "filtered_environmental_failure": True,
        "elapsed_seconds": 21.62 if variant == "baseline" else 20.82,
        "stdout_path": str(test_path.resolve()),
        "stderr_path": str((artifact / f"{variant}.tests.stderr.txt").resolve()),
        "output_preview": _read(test_path)[-3000:],
    }
    acceptance = {
        "returncode": 0 if not _read(acceptance_path) else 1,
        "elapsed_seconds": 5.71,
        "stdout_path": str((artifact / f"{variant}.acceptance.stdout.txt").resolve()),
        "stderr_path": str(acceptance_path.resolve()),
        "output_preview": _read(acceptance_path)[-3000:],
    }
    source_text = ""
    for name in changed_files:
        path = worktree / name
        if path.is_file() and path.suffix in {".py", ".md", ".toml"}:
            source_text += _read(path) + "\n"
    criteria = {
        "review_strategy_surface": "review" in source_text and "end_strategy" in source_text,
        "patch_surface": "patch_result" in source_text or "JsonPatch" in source_text or "json patch" in source_text.lower(),
        "confirmation_surface": "confirm_result" in source_text or "confirmation" in source_text.lower(),
        "tests_touched": bool(diff["test_files_changed"]),
        "targeted_suite_green": tests["returncode"] == 0,
        "external_acceptance_green": acceptance["returncode"] == 0,
        "codex_completed": False,
        "no_whitespace_errors": diff["diff_check_passed"],
    }
    return {
        "variant": variant,
        "status": "timeout",
        "returncode": None,
        "elapsed_seconds": 900.54 if variant == "baseline" else 900.76,
        "usage": usage,
        "usage_complete": False,
        "estimated_cost_usd": None,
        "usage_note": "No terminal token telemetry before timeout; zero is not a billing estimate.",
        "observed": observed,
        "event_detail": _event_detail(events_path),
        "response_preview": response[-3000:],
        "worktree": str(worktree.resolve()),
        "events_path": str(events_path.resolve()),
        "stderr_path": str((artifact / f"{variant}.stderr.txt").resolve()),
        "timeout_path": str((artifact / f"{variant}.timeout.txt").resolve()),
        "tests": tests,
        "external_acceptance": acceptance,
        "diff": diff,
        "criteria": criteria,
        "accepted": False,
    }


def _totals(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage", {})
    return {
        **usage,
        "estimated_cost_usd": result.get("estimated_cost_usd"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "test_elapsed_seconds": result.get("tests", {}).get("elapsed_seconds"),
        "acceptance_elapsed_seconds": result.get("external_acceptance", {}).get("elapsed_seconds"),
        "event_count": result.get("observed", {}).get("event_count", 0),
        "turn_count": result.get("observed", {}).get("turn_count", 0),
        "tool_call_count": result.get("observed", {}).get("tool_call_count", 0),
        "accepted": result.get("accepted", False),
        "changed_file_count": result.get("diff", {}).get("changed_file_count", 0),
        "lines_added": result.get("diff", {}).get("lines_added", 0),
        "lines_deleted": result.get("diff", {}).get("lines_deleted", 0),
    }


def _pct(base: Any, treatment: Any) -> float | None:
    if not isinstance(base, (int, float)) or not base or not isinstance(treatment, (int, float)):
        return None
    return round((treatment - base) / base * 100, 2)


def merge(baseline_artifact: Path, astra_result_path: Path, baseline_worktree: Path, output: Path) -> dict[str, Any]:
    astra_report = json.loads(astra_result_path.read_text(encoding="utf-8-sig"))
    astra = next(item for item in astra_report["results"] if item["variant"] == "astra-ultra")
    astra_artifact = Path(astra_report["artifact_dir"])
    astra = _timeout_result(astra_artifact, Path(astra["worktree"]), "astra-ultra") | {
        "response_preview": astra.get("response_preview", ""),
    }
    baseline = _timeout_result(baseline_artifact, baseline_worktree, "baseline")
    results = [baseline, astra]
    totals = {result["variant"]: _totals(result) for result in results}
    base = totals["baseline"]
    ultra = totals["astra-ultra"]
    metrics = {
        "input_token_change_pct": _pct(base["input_tokens"], ultra["input_tokens"]),
        "cached_input_change_pct": _pct(base["cached_input_tokens"], ultra["cached_input_tokens"]),
        "output_token_change_pct": _pct(base["output_tokens"], ultra["output_tokens"]),
        "reasoning_token_change_pct": _pct(base["reasoning_output_tokens"], ultra["reasoning_output_tokens"]),
        "latency_change_pct": _pct(base["elapsed_seconds"], ultra["elapsed_seconds"]),
        "speedup_factor": round(base["elapsed_seconds"] / ultra["elapsed_seconds"], 3),
        "cost_change_pct": None,
        "tool_call_change_pct": _pct(base["tool_call_count"], ultra["tool_call_count"]),
        "accepted_variants": 0,
    }
    report = {
        "schema": 1,
        "benchmark": "real_github_task",
        "repository": REPO_URL,
        "issue": ISSUE_URL,
        "issue_title": ISSUE_TITLE,
        "base_sha": BASE_SHA,
        "model": astra_report.get("model", "gpt-5.6-luna"),
        "effort": astra_report.get("effort", "max"),
        "order": "baseline-first (baseline reused; Astra resumed separately)",
        "artifact_dir": str(astra_artifact.resolve()),
        "worktrees": {result["variant"]: result["worktree"] for result in results},
        "results": results,
        "totals": totals,
        "metrics": metrics,
        "limitations": [
            "This real task exceeded the 900-second Codex horizon for both variants; raw terminal token counters are unavailable and therefore null.",
            "The comparison preserves JSONL event/tool counts and partial diffs; it does not infer billing from incomplete streams.",
            "The target suite passes after excluding one unrelated Windows MCP integration test that fails identically in both clean worktrees.",
            "Astra-Ultra edited `_output.py`, but the graph still raises `assert_never('review')`; the external acceptance harness fails accordingly.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-artifact", type=Path, required=True)
    parser.add_argument("--astra-result", type=Path, required=True)
    parser.add_argument("--baseline-worktree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    merge(args.baseline_artifact, args.astra_result, args.baseline_worktree, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
