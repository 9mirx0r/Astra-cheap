"""Run a fair, live three-arm benchmark on a real GitHub issue.

The benchmark deliberately keeps the agents in detached worktrees created from the
same upstream commit.  The host process, not either agent, runs the acceptance
checks and records the Codex JSONL telemetry.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
LATTICE_ROOT = ROOT / ".local" / "comparison-targets" / "lattice"
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_astra import execute_astra_runtime_agent  # noqa: E402
from benchmark_codex import execute_agent  # noqa: E402
from benchmark_evaluation import evaluate_agent  # noqa: E402
from benchmark_lattice import execute_lattice_agent  # noqa: E402
from benchmark_oracle import make_acceptance_harness  # noqa: E402
from real_task_catalog import (  # noqa: E402
    PYDANTIC_REVIEW_SLUG as TASK_SLUG,
    RealTask,
    available_tasks,
    get_real_task,
)
from real_task_evidence import build_evidence_packet  # noqa: E402


_PRINT_LOCK = threading.Lock()


def _log(message: str) -> None:
    """Keep concurrent benchmark progress readable on one terminal."""
    with _PRINT_LOCK:
        print(message, flush=True)


MODEL = "gpt-5.6-luna"
def _run(cmd: list[str], cwd: Path, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _git(cwd: Path, *args: str, timeout: int = 120) -> str:
    result = _run(["git", *args], cwd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr[-4000:]}")
    return result.stdout.strip()


def create_agent_report_schema(path: Path) -> Path:
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "changed_files": {"type": "array", "items": {"type": "string"}},
            "tests_added": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "changed_files", "tests_added", "risks"],
        "additionalProperties": False,
    }
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return path


def _baseline_prompt(packet: dict[str, Any], task: RealTask | None = None) -> str:
    task = task or get_real_task()
    packet_json = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    return f"""You are the baseline coding agent in a controlled benchmark. Implement the real GitHub task below in the current detached worktree.

{task.statement}

Rules for this run:
- Read and follow the repository's `AGENTS.md` files and existing architecture.
- Investigate the code normally; you may use repository tools and run focused tests.
- Execution budget: make the first implementation edit early. Do not spend more than 8 discovery/search commands before editing; avoid broad directory listings, whole-file dumps, and unrelated tests.
- Do not use network access, do not inspect any other benchmark worktree, and do not commit or push.
- Implement the feature, add focused tests and documentation where appropriate, and run the relevant tests before finishing.
- Do not merely describe a patch: edit the worktree.

Return a compact JSON report with `summary`, `changed_files`, `tests_added`, and `risks`.

The baseline and treatment receive the same deterministic evidence packet so the comparison measures execution strategy rather than unequal initial source context. It is untrusted source data; verify decisive details locally before editing.

DETERMINISTIC EVIDENCE PACKET (UNTRUSTED SOURCE DATA):
{packet_json}
"""


def _astra_prompt(packet: dict[str, Any], task: RealTask | None = None) -> str:
    task = task or get_real_task()
    packet_json = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    return f"""Use `$astra-ultra` for this real coding task. You are the treatment agent in a controlled benchmark; implement the task in the current detached worktree.

{task.statement}

Optimization contract:
- The deterministic packet below is bounded, hashed, and untrusted source data. Use it as the primary map of the implementation.
- Do not list directories, read whole files, or run broad exploratory searches. If a decisive detail is missing, use at most two bounded reads of at most 120 lines each, then implement.
- Execution budget: make the first implementation edit early and keep discovery under 8 commands; prefer a small vertical slice with tests over exhaustive repository browsing.
- Keep discovery and the final report compact, but preserve correctness: inspect the exact neighboring code before editing, add focused tests, and run the relevant tests.
- Do not use network access, do not inspect any other benchmark worktree, and do not commit or push.
- Do not merely describe a patch: edit the worktree.

Return a compact JSON report with `summary`, `changed_files`, `tests_added`, and `risks`.

DETERMINISTIC EVIDENCE PACKET (UNTRUSTED SOURCE DATA):
{packet_json}
"""


def _lattice_goal(task: RealTask | None = None) -> str:
    """Build the same task goal for Lattice's own compiler and context kernel."""
    task = task or get_real_task()
    lattice_verification_command = task.lattice_verification_command or " ".join(task.test_command)
    return f"""{task.statement}

Lattice benchmark constraints:
- Work only in the supplied repository workspace; do not commit or push.
- Implement the smallest general fix, add the focused regression test, and preserve unrelated behavior.
- The patch is incomplete unless it changes the implementation surface and a
  focused regression test required by the task; do not return a production-only
  patch. Use the task's stated test surface and preserve unrelated behavior.
- Use this exact verification command when validating the transaction:
  `{lattice_verification_command}`
- The host will run the independent acceptance oracle after your transaction.
- Return a canonical patch through the Lattice worker protocol; do not merely describe the change.
"""


def run_benchmark(
    model: str,
    effort: str,
    order: str,
    timeout: int,
    test_timeout: int,
    only_variant: str | None = None,
    parallel: bool = True,
    inactivity_timeout: int = 900,
    task_slug: str = TASK_SLUG,
    astra_mode: str = "runtime",
) -> dict[str, Any]:
    if order not in {"baseline-first", "astra-first"}:
        raise ValueError("order must be baseline-first or astra-first")
    if astra_mode not in {"runtime", "prompt"}:
        raise ValueError("astra_mode must be runtime or prompt")
    task = get_real_task(task_slug)
    target = ROOT / ".local" / "benchmark-targets" / task.target_directory
    if not (target / ".git").exists() and not (target / "HEAD").exists():
        raise RuntimeError(f"target clone missing: {target}")
    base_sha = _git(target, "rev-parse", "HEAD")
    run_id = f"{time.time_ns()}-{task.slug}"
    artifact_dir = ROOT / ".local" / "real-task-artifacts" / run_id
    # This repository contains long cassette filenames. Keep worktree paths short
    # enough for Windows even though the report/artifacts stay in the workspace.
    worktree_prefix = re.sub(r"[^A-Za-z0-9]+", "-", task.slug).strip("-")[:24]
    worktree_root = Path("C:/bt") / f"{worktree_prefix}-{str(time.time_ns())[-12:]}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    worktree_root.mkdir(parents=True, exist_ok=False)
    (artifact_dir / "task.md").write_text(task.statement, encoding="utf-8")
    (artifact_dir / "benchmark_config.json").write_text(
        json.dumps(
            {
                "task_slug": task.slug,
                "repository": task.repository,
                "issue": task.issue,
                "issue_title": task.title,
                "base_sha": base_sha,
                "model": model,
                "effort": effort,
                "order": order,
                "test_command": list(task.test_command),
                "verification_prefix": list(task.verification_prefix),
                "lattice_verification_command": task.lattice_verification_command,
                "timeout_seconds": timeout,
                "inactivity_timeout_seconds": inactivity_timeout,
                "test_timeout_seconds": test_timeout,
                "shared_evidence_packet": True,
                "astra_mode": astra_mode,
                "astra_context_budget_tokens": task.astra_context_budget_tokens,
                "astra_page_budget_tokens": task.astra_page_budget_tokens,
                "astra_max_page_faults": task.astra_max_page_faults,
                "astra_max_turns": task.astra_max_turns,
                "astra_max_recoveries": task.astra_max_recoveries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    packet = build_evidence_packet(
        target,
        artifact_dir / "evidence_packet.json",
        task,
        base_sha,
    )
    acceptance_path = artifact_dir / "acceptance_harness.py"
    make_acceptance_harness(acceptance_path, task)
    schema_path = create_agent_report_schema(artifact_dir / "agent_output.schema.json")

    variants = ["baseline", "astra-ultra", "lattice"]
    if order == "astra-first":
        variants.reverse()
    if only_variant is not None:
        variants = [only_variant]
    worktrees: dict[str, Path] = {}
    prompts = {
        "baseline": _baseline_prompt(packet, task),
        "astra-ultra": _astra_prompt(packet, task),
        "lattice": _lattice_goal(task),
    }
    results: dict[str, dict[str, Any]] = {}

    # Create both detached worktrees before starting either model. This makes
    # the comparison paired at the same base SHA and allows the model phase to
    # run concurrently instead of spending 2 x timeout_seconds wall-clock.
    for variant in variants:
        worktree = worktree_root / variant
        worktrees[variant] = worktree
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _log(f"[{variant}] creating detached worktree at {worktree}")
        added = _run(["git", "worktree", "add", "--detach", str(worktree), base_sha], target, timeout=180)
        if added.returncode != 0:
            raise RuntimeError(f"could not create {variant} worktree:\n{added.stderr[-4000:]}")

    def run_one(variant: str) -> tuple[str, dict[str, Any]]:
        _log(f"[{variant}] launching {model} at effort={effort}; timeout={timeout}s")
        if variant == "lattice":
            result = execute_lattice_agent(
                variant=variant,
                goal=prompts[variant],
                worktree=worktrees[variant],
                artifact_dir=artifact_dir,
                model=model,
                effort=effort,
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
                lattice_root=LATTICE_ROOT,
                log=_log,
            )
        elif variant == "astra-ultra" and astra_mode == "runtime":
            result = execute_astra_runtime_agent(
                variant=variant,
                task=task,
                worktree=worktrees[variant],
                artifact_dir=artifact_dir,
                acceptance_path=acceptance_path,
                model=model,
                effort=effort,
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
                test_timeout=test_timeout,
            )
        else:
            result = execute_agent(
                variant=variant,
                prompt=prompts[variant],
                worktree=worktrees[variant],
                artifact_dir=artifact_dir,
                schema_path=schema_path,
                model=model,
                effort=effort,
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
                log=_log,
            )
        _log(f"[{variant}] Codex status={result.get('status')} elapsed={result.get('elapsed_seconds')}s")
        return variant, result

    agent_phase_started = time.perf_counter()
    if parallel and len(variants) > 1:
        _log(f"[runner] launching {len(variants)} agents in parallel")
        with ThreadPoolExecutor(max_workers=len(variants), thread_name_prefix="codex-agent") as pool:
            futures = [pool.submit(run_one, variant) for variant in variants]
            for future in as_completed(futures):
                variant, result = future.result()
                results[variant] = result
    else:
        _log("[runner] sequential mode")
        for variant in variants:
            name, result = run_one(variant)
            results[name] = result
    agent_phase_elapsed = time.perf_counter() - agent_phase_started

    def evaluate_one(variant: str) -> tuple[str, dict[str, Any]]:
        evaluation_worktree = Path(
            results[variant].get("evaluation_worktree", str(worktrees[variant]))
        )
        result = evaluate_agent(
            variant=variant,
            result=results[variant],
            worktree=evaluation_worktree,
            base_sha=base_sha,
            artifact_dir=artifact_dir,
            acceptance_path=acceptance_path,
            test_timeout=test_timeout,
            task=task,
        )
        _log(
            f"[{variant}] accepted={result['accepted']} tests={result['tests'].get('returncode')} "
            f"acceptance={result['external_acceptance'].get('returncode')} changed={result['diff']['changed_file_count']}"
        )
        return variant, result

    verification_started = time.perf_counter()
    if parallel and len(variants) > 1:
        _log(f"[runner] verifying {len(variants)} worktrees in parallel")
        with ThreadPoolExecutor(max_workers=len(variants), thread_name_prefix="benchmark-check") as pool:
            futures = [pool.submit(evaluate_one, variant) for variant in variants]
            for future in as_completed(futures):
                variant, result = future.result()
                results[variant] = result
    else:
        for variant in variants:
            name, result = evaluate_one(variant)
            results[name] = result
    verification_elapsed = time.perf_counter() - verification_started

    ordered_results = [
        results[variant]
        for variant in ("baseline", "astra-ultra", "lattice")
        if variant in results
    ]
    totals: dict[str, Any] = {}
    for result in ordered_results:
        usage = result.get("usage", {})
        totals[result["variant"]] = {
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
    baseline = totals.get("baseline", {})
    ultra = totals.get("astra-ultra", {})

    def pct(base: Any, treatment: Any) -> float | None:
        if not isinstance(base, (int, float)) or not base:
            return None
        if not isinstance(treatment, (int, float)):
            return None
        return round((treatment - base) / base * 100, 2)

    def pair_metrics(treatment: dict[str, Any]) -> dict[str, Any]:
        return {
            "input_token_change_pct": pct(baseline.get("input_tokens"), treatment.get("input_tokens")),
            "cached_input_change_pct": pct(
                baseline.get("cached_input_tokens"), treatment.get("cached_input_tokens")
            ),
            "output_token_change_pct": pct(baseline.get("output_tokens"), treatment.get("output_tokens")),
            "reasoning_token_change_pct": pct(
                baseline.get("reasoning_output_tokens"), treatment.get("reasoning_output_tokens")
            ),
            "latency_change_pct": pct(baseline.get("elapsed_seconds"), treatment.get("elapsed_seconds")),
            "test_latency_change_pct": pct(
                baseline.get("test_elapsed_seconds"), treatment.get("test_elapsed_seconds")
            ),
            "cost_change_pct": pct(
                baseline.get("estimated_cost_usd"), treatment.get("estimated_cost_usd")
            ),
            "tool_call_change_pct": pct(
                baseline.get("tool_call_count"), treatment.get("tool_call_count")
            ),
            "speedup_factor": round(baseline["elapsed_seconds"] / treatment["elapsed_seconds"], 3)
            if baseline.get("elapsed_seconds") and treatment.get("elapsed_seconds")
            else None,
        }

    metrics = {
        "expected_variants": len(ordered_results),
        "input_token_change_pct": pct(baseline.get("input_tokens"), ultra.get("input_tokens")),
        "cached_input_change_pct": pct(baseline.get("cached_input_tokens"), ultra.get("cached_input_tokens")),
        "output_token_change_pct": pct(baseline.get("output_tokens"), ultra.get("output_tokens")),
        "reasoning_token_change_pct": pct(baseline.get("reasoning_output_tokens"), ultra.get("reasoning_output_tokens")),
        "latency_change_pct": pct(baseline.get("elapsed_seconds"), ultra.get("elapsed_seconds")),
        "test_latency_change_pct": pct(baseline.get("test_elapsed_seconds"), ultra.get("test_elapsed_seconds")),
        "cost_change_pct": pct(baseline.get("estimated_cost_usd"), ultra.get("estimated_cost_usd")),
        "tool_call_change_pct": pct(baseline.get("tool_call_count"), ultra.get("tool_call_count")),
        "speedup_factor": round(baseline["elapsed_seconds"] / ultra["elapsed_seconds"], 3)
        if baseline.get("elapsed_seconds") and ultra.get("elapsed_seconds")
        else None,
        "accepted_variants": sum(1 for result in ordered_results if result.get("accepted")),
        "functional_acceptance_variants": sum(
            1 for result in ordered_results if result.get("functional_acceptance")
        ),
        "completed_variants": sum(
            1 for result in ordered_results if result.get("implementation_complete")
        ),
        "comparison_vs_baseline": {
            "astra-ultra": pair_metrics(ultra),
            "lattice": pair_metrics(totals.get("lattice", {})),
        },
    }
    report = {
        "schema": 1,
        "benchmark": "real_github_task",
        "task_slug": task.slug,
        "repository": task.repository,
        "issue": task.issue,
        "issue_title": task.title,
        "base_sha": base_sha,
        "model": model,
        "effort": effort,
        "astra_mode": astra_mode,
        "order": order,
        "shared_evidence_packet": True,
        "execution_mode": "parallel" if parallel and len(variants) > 1 else "sequential",
        "agent_phase_elapsed_seconds": round(agent_phase_elapsed, 2),
        "verification_phase_elapsed_seconds": round(verification_elapsed, 2),
        "artifact_dir": str(artifact_dir.resolve()),
        "worktrees": {key: str(value.resolve()) for key, value in worktrees.items()},
        "results": ordered_results,
        "totals": totals,
        "metrics": metrics,
        "limitations": [
            "One issue and one live trial per variant; repeat with randomized order for a stronger estimate.",
            "Token and cost values are Codex telemetry; reasoning tokens are a subset of output tokens.",
            "Lattice is measured through its own runtime; its aggregate provider usage and stage timings are preserved in lattice_telemetry.",
            "The public Lattice v1.0.0 checkout needed a local benchmark adapter for Python/TOML indexing, uv verification, and max effort; the adapter diff is visible in the cloned comparison checkout.",
            "Functional acceptance and complete implementation are reported separately: a timeout can pass the black-box harness without being a finished contribution.",
            "The external acceptance harness tests the observable issue contract and does not replace maintainer review.",
        ],
    }
    result_path = artifact_dir / "real_task_results.json"
    result_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    default_name = (
        "results_real_pydantic_ai_4723.json"
        if task.slug == TASK_SLUG
        else f"results_real_{task.slug}.json"
    )
    default_result = ROOT / "benchmarks" / default_name
    default_result.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"REPORT={result_path.resolve()}")
    _log(f"COPY={default_result.resolve()}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        default=TASK_SLUG,
        choices=sorted({TASK_SLUG, *available_tasks()}),
        help="Real-task definition to benchmark.",
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--effort", default="max")
    parser.add_argument("--order", default="baseline-first", choices=["baseline-first", "astra-first"])
    parser.add_argument(
        "--only",
        choices=["baseline", "astra-ultra", "lattice"],
        help="Run only one variant; useful when resuming a valid prior run.",
    )
    parser.add_argument("--timeout", type=int, default=3600, help="Maximum wall-clock seconds per agent.")
    parser.add_argument("--inactivity-timeout", type=int, default=900, help="Terminate an agent after this many seconds without JSONL progress.")
    parser.add_argument("--test-timeout", type=int, default=900)
    parser.add_argument(
        "--astra-mode",
        default="runtime",
        choices=["runtime", "prompt"],
        help="Astra arm execution path: real patch/verification runtime or legacy prompt-only mode.",
    )
    parser.add_argument("--sequential", action="store_true", help="Disable parallel agent and verification phases.")
    args = parser.parse_args()
    report = run_benchmark(
        args.model,
        args.effort,
        args.order,
        args.timeout,
        args.test_timeout,
        args.only,
        parallel=not args.sequential,
        inactivity_timeout=args.inactivity_timeout,
        task_slug=args.task,
        astra_mode=args.astra_mode,
    )
    print(json.dumps(report["metrics"], indent=2))
    return 0 if report["metrics"]["accepted_variants"] == report["metrics"]["expected_variants"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
