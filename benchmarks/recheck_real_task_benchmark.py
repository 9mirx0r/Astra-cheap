"""Re-run host-side tests and acceptance for an already completed live trial.

This is intentionally separate from the model phase: if the acceptance harness
is corrected, an hour-long pair does not need to be spent again just to refresh
the host-side verdict.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from run_real_task_benchmark import (  # noqa: E402
    _log,
    get_real_task,
    make_acceptance_harness,
)
from benchmark_evaluation import evaluate_agent  # noqa: E402


def _pct(base: Any, treatment: Any) -> float | None:
    if not isinstance(base, (int, float)) or not base or not isinstance(treatment, (int, float)):
        return None
    return round((treatment - base) / base * 100, 2)


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
        "functional_acceptance": result.get("functional_acceptance", False),
        "implementation_complete": result.get("implementation_complete", False),
        "changed_file_count": result.get("diff", {}).get("changed_file_count", 0),
        "lines_added": result.get("diff", {}).get("lines_added", 0),
        "lines_deleted": result.get("diff", {}).get("lines_deleted", 0),
    }


def recheck(report_path: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    artifact_dir = Path(report["artifact_dir"])
    acceptance_path = artifact_dir / "acceptance_harness.py"
    task = get_real_task(report.get("task_slug", "pydantic-ai-4723-review-output"))
    make_acceptance_harness(acceptance_path, task)
    base_sha = report["base_sha"]
    test_timeout = int(json.loads((artifact_dir / "benchmark_config.json").read_text())["test_timeout_seconds"])
    results_by_variant = {item["variant"]: item for item in report["results"]}

    def check(variant: str) -> tuple[str, dict[str, Any]]:
        item = results_by_variant[variant]
        result = evaluate_agent(
            variant=variant,
            result=item,
            worktree=Path(item["worktree"]),
            base_sha=base_sha,
            artifact_dir=artifact_dir,
            acceptance_path=acceptance_path,
            test_timeout=test_timeout,
            task=task,
        )
        _log(
            f"[{variant}] recheck complete={result['implementation_complete']} "
            f"functional={result['functional_acceptance']} tests={result['tests'].get('returncode')} "
            f"acceptance={result['external_acceptance'].get('returncode')}"
        )
        return variant, result

    checked: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=len(results_by_variant), thread_name_prefix="benchmark-recheck") as pool:
        futures = [pool.submit(check, variant) for variant in results_by_variant]
        for future in as_completed(futures):
            variant, result = future.result()
            checked[variant] = result

    ordered = [checked[variant] for variant in ("baseline", "astra-ultra") if variant in checked]
    totals = {result["variant"]: _totals(result) for result in ordered}
    baseline = totals.get("baseline", {})
    ultra = totals.get("astra-ultra", {})
    report["results"] = ordered
    report["totals"] = totals
    report["recheck"] = {
        "acceptance_harness": "output_tools + function_tools; confirm/finalize/review aliases",
        "host_side_tests_rerun": True,
    }
    report["metrics"] = {
        "input_token_change_pct": _pct(baseline.get("input_tokens"), ultra.get("input_tokens")),
        "cached_input_change_pct": _pct(baseline.get("cached_input_tokens"), ultra.get("cached_input_tokens")),
        "output_token_change_pct": _pct(baseline.get("output_tokens"), ultra.get("output_tokens")),
        "reasoning_token_change_pct": _pct(
            baseline.get("reasoning_output_tokens"), ultra.get("reasoning_output_tokens")
        ),
        "latency_change_pct": _pct(baseline.get("elapsed_seconds"), ultra.get("elapsed_seconds")),
        "test_latency_change_pct": _pct(baseline.get("test_elapsed_seconds"), ultra.get("test_elapsed_seconds")),
        "cost_change_pct": _pct(baseline.get("estimated_cost_usd"), ultra.get("estimated_cost_usd")),
        "tool_call_change_pct": _pct(baseline.get("tool_call_count"), ultra.get("tool_call_count")),
        "speedup_factor": round(baseline["elapsed_seconds"] / ultra["elapsed_seconds"], 3)
        if baseline.get("elapsed_seconds") and ultra.get("elapsed_seconds")
        else None,
        "accepted_variants": sum(1 for result in ordered if result.get("accepted")),
        "functional_acceptance_variants": sum(1 for result in ordered if result.get("functional_acceptance")),
        "completed_variants": sum(1 for result in ordered if result.get("implementation_complete")),
    }
    report["limitations"] = [
        "Baseline timed out before terminal usage telemetry; its token and cost fields remain unavailable.",
        "Astra-Ultra completed and has terminal token telemetry; cost is estimated from the configured rate card.",
        "Functional acceptance and complete implementation are reported separately.",
        "The targeted suite excludes the unrelated Windows MCP integration test that fails in clean worktrees.",
    ]
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    default_name = (
        "results_real_pydantic_ai_4723.json"
        if task.slug == "pydantic-ai-4723-review-output"
        else f"results_real_{task.slug}.json"
    )
    default_result = ROOT / "benchmarks" / default_name
    default_result.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path.resolve())
    print(default_result.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    report = recheck(args.input)
    return 0 if report["metrics"]["functional_acceptance_variants"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
