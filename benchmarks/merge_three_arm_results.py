"""Merge a paired three-arm report with a later validated Astra retry."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


ORDER = ("baseline", "astra-ultra", "lattice")


def _pct(base: Any, treatment: Any) -> float | None:
    if not isinstance(base, (int, float)) or not base:
        return None
    if not isinstance(treatment, (int, float)):
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
        "changed_file_count": result.get("diff", {}).get("changed_file_count", 0),
        "lines_added": result.get("diff", {}).get("lines_added", 0),
        "lines_deleted": result.get("diff", {}).get("lines_deleted", 0),
    }


def _pair_metrics(baseline: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_token_change_pct": _pct(baseline.get("input_tokens"), treatment.get("input_tokens")),
        "cached_input_change_pct": _pct(
            baseline.get("cached_input_tokens"), treatment.get("cached_input_tokens")
        ),
        "output_token_change_pct": _pct(baseline.get("output_tokens"), treatment.get("output_tokens")),
        "reasoning_token_change_pct": _pct(
            baseline.get("reasoning_output_tokens"), treatment.get("reasoning_output_tokens")
        ),
        "latency_change_pct": _pct(baseline.get("elapsed_seconds"), treatment.get("elapsed_seconds")),
        "test_latency_change_pct": _pct(
            baseline.get("test_elapsed_seconds"), treatment.get("test_elapsed_seconds")
        ),
        "cost_change_pct": _pct(baseline.get("estimated_cost_usd"), treatment.get("estimated_cost_usd")),
        "tool_call_change_pct": _pct(
            baseline.get("tool_call_count"), treatment.get("tool_call_count")
        ),
        "speedup_factor": (
            round(baseline["elapsed_seconds"] / treatment["elapsed_seconds"], 3)
            if baseline.get("elapsed_seconds") and treatment.get("elapsed_seconds")
            else None
        ),
    }


def merge(base_path: Path, astra_path: Path, output_path: Path) -> dict[str, Any]:
    base = json.loads(base_path.read_text(encoding="utf-8-sig"))
    retry = json.loads(astra_path.read_text(encoding="utf-8-sig"))
    by_variant = {item["variant"]: copy.deepcopy(item) for item in base.get("results", [])}
    retry_astra = next(item for item in retry.get("results", []) if item.get("variant") == "astra-ultra")
    by_variant["astra-ultra"] = copy.deepcopy(retry_astra)
    results = [by_variant[name] for name in ORDER if name in by_variant]
    totals = {item["variant"]: _totals(item) for item in results}
    baseline = totals.get("baseline", {})
    ultra = totals.get("astra-ultra", {})
    metrics = {
        "expected_variants": len(results),
        "input_token_change_pct": _pct(baseline.get("input_tokens"), ultra.get("input_tokens")),
        "cached_input_change_pct": _pct(
            baseline.get("cached_input_tokens"), ultra.get("cached_input_tokens")
        ),
        "output_token_change_pct": _pct(baseline.get("output_tokens"), ultra.get("output_tokens")),
        "reasoning_token_change_pct": _pct(
            baseline.get("reasoning_output_tokens"), ultra.get("reasoning_output_tokens")
        ),
        "latency_change_pct": _pct(baseline.get("elapsed_seconds"), ultra.get("elapsed_seconds")),
        "test_latency_change_pct": _pct(
            baseline.get("test_elapsed_seconds"), ultra.get("test_elapsed_seconds")
        ),
        "cost_change_pct": _pct(baseline.get("estimated_cost_usd"), ultra.get("estimated_cost_usd")),
        "tool_call_change_pct": _pct(
            baseline.get("tool_call_count"), ultra.get("tool_call_count")
        ),
        "speedup_factor": (
            round(baseline["elapsed_seconds"] / ultra["elapsed_seconds"], 3)
            if baseline.get("elapsed_seconds") and ultra.get("elapsed_seconds")
            else None
        ),
        "accepted_variants": sum(1 for item in results if item.get("accepted")),
        "functional_acceptance_variants": sum(1 for item in results if item.get("functional_acceptance")),
        "completed_variants": sum(1 for item in results if item.get("implementation_complete")),
        "comparison_vs_baseline": {
            "astra-ultra": _pair_metrics(baseline, ultra),
            "lattice": _pair_metrics(baseline, totals.get("lattice", {})),
        },
    }
    merged = copy.deepcopy(base)
    merged["results"] = results
    merged["totals"] = totals
    merged["metrics"] = metrics
    merged["artifact_dir"] = str(output_path.parent.resolve())
    merged["worktrees"] = {
        name: item.get("worktree") for name, item in ((item["variant"], item) for item in results)
    }
    merged["execution_mode"] = "paired baseline/lattice + validated Astra retry"
    merged["source_reports"] = {
        "paired_three_arm": str(base_path.resolve()),
        "astra_retry": str(astra_path.resolve()),
    }
    merged.setdefault("limitations", []).append(
        "Astra-Ultra is a validated retry from the same base SHA after host-runtime fixes; "
        "baseline and Lattice are retained from the paired run."
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path, help="Original paired three-arm report")
    parser.add_argument("--astra", required=True, type=Path, help="Validated Astra-only retry report")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = merge(args.base, args.astra, args.output)
    print(json.dumps(report["metrics"], indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
