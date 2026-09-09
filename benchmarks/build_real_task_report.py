"""Build a self-contained HTML report for a real-task benchmark result."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.5f}" if abs(value) < 1 else f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return html.escape(str(value))


def _pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def _bar(label: str, baseline: Any, ultra: Any, unit: str = "") -> str:
    base = float(baseline or 0)
    treatment = float(ultra or 0)
    scale = max(base, treatment, 1.0)
    base_width = max(0.0, min(100.0, base / scale * 100))
    ultra_width = max(0.0, min(100.0, treatment / scale * 100))
    return f"""<div class="bar-row">
      <div class="bar-label"><span>{html.escape(label)} · baseline</span><span>{_fmt(baseline)} {unit}</span></div>
      <div class="track"><div class="fill base" style="width:{base_width:.2f}%"></div></div>
      <div class="bar-label"><span>{html.escape(label)} · Astra-Ultra</span><span>{_fmt(ultra)} {unit}</span></div>
      <div class="track"><div class="fill ultra" style="width:{ultra_width:.2f}%"></div></div>
    </div>"""


def build_html(report: dict[str, Any]) -> str:
    totals = report.get("totals", {})
    baseline = totals.get("baseline", {})
    ultra = totals.get("astra-ultra", {})
    metrics = report.get("metrics", {})
    results = {item.get("variant"): item for item in report.get("results", [])}

    rows = [
        ("Input tokens", "input_tokens", "tokens"),
        ("Cached input", "cached_input_tokens", "tokens"),
        ("Cache-write input", "cache_write_input_tokens", "tokens"),
        ("Output tokens", "output_tokens", "tokens"),
        ("Reasoning output (subset)", "reasoning_output_tokens", "tokens"),
        ("Estimated cost", "estimated_cost_usd", "USD"),
        ("Codex elapsed", "elapsed_seconds", "seconds"),
        ("Target tests elapsed", "test_elapsed_seconds", "seconds"),
        ("Acceptance elapsed", "acceptance_elapsed_seconds", "seconds"),
        ("JSONL events", "event_count", "events"),
        ("Turns", "turn_count", "turns"),
        ("Tool calls", "tool_call_count", "calls"),
        ("Files changed", "changed_file_count", "files"),
        ("Lines added", "lines_added", "lines"),
        ("Lines deleted", "lines_deleted", "lines"),
    ]
    table = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{_fmt(baseline.get(key))}</td><td>{_fmt(ultra.get(key))}</td></tr>"
        for label, key, _unit in rows
    )
    chart = "\n".join(_bar(label, baseline.get(key), ultra.get(key), unit) for label, key, unit in rows[:7])

    criteria = sorted(
        set().union(*(item.get("criteria", {}).keys() for item in results.values() if isinstance(item, dict)))
    )
    criteria_rows = "\n".join(
        f"<tr><th>{html.escape(name)}</th>"
        + "".join(
            f"<td class={'pass' if results.get(variant, {}).get('criteria', {}).get(name) else 'fail'}>"
            f"{'PASS' if results.get(variant, {}).get('criteria', {}).get(name) else 'FAIL'}</td>"
            for variant in ("baseline", "astra-ultra")
        )
        + "</tr>"
        for name in criteria
    )
    issue = html.escape(str(report.get("issue", "")))
    repo = html.escape(str(report.get("repository", "")))
    title = html.escape(str(report.get("issue_title", "Real GitHub task")))
    accepted = metrics.get("accepted_variants", 0)
    functional = metrics.get("functional_acceptance_variants", 0)
    completed = metrics.get("completed_variants", accepted)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Real task benchmark · Astra-Ultra</title>
<style>
:root {{ color-scheme: dark; --bg:#0b1020; --panel:#131b31; --line:#273452; --text:#e8eefc; --muted:#9aa9c7; --base:#fb7185; --ultra:#34d399; --accent:#7dd3fc; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:radial-gradient(circle at top right,#16213c 0,#0b1020 48%); color:var(--text); font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:36px 22px 64px; }} h1 {{ margin:0 0 8px; font-size:30px; }} h2 {{ margin:30px 0 12px; font-size:19px; }} p, .muted {{ color:var(--muted); }} a {{ color:var(--accent); }} code {{ color:#c4b5fd; }}
.meta {{ background:rgba(19,27,49,.85); border:1px solid var(--line); border-radius:14px; padding:18px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-top:18px; }} .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; }} .card small {{ display:block; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }} .card strong {{ display:block; margin-top:5px; font-size:25px; }}
.panel {{ margin-top:18px; background:rgba(19,27,49,.82); border:1px solid var(--line); border-radius:14px; padding:18px; overflow:auto; }} table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:right; }} th:first-child,td:first-child {{ text-align:left; }} thead th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
.base {{ color:var(--base); }} .ultra {{ color:var(--ultra); }} .pass {{ color:var(--ultra); font-weight:700; }} .fail {{ color:var(--base); font-weight:700; }}
.bar-row {{ margin:17px 0 22px; }} .bar-label {{ display:flex; justify-content:space-between; color:var(--muted); margin:5px 0; }} .track {{ height:13px; background:#26324d; border-radius:99px; overflow:hidden; }} .fill {{ height:100%; border-radius:99px; }} .fill.base {{ background:var(--base); }} .fill.ultra {{ background:var(--ultra); }}
.legend {{ display:flex; gap:16px; color:var(--muted); }} .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; }} .dot.base {{ background:var(--base); }} .dot.ultra {{ background:var(--ultra); }}
@media(max-width:650px) {{ h1 {{font-size:23px}} .bar-label {{gap:12px; font-size:12px}} }}
</style></head><body><main>
<div class="meta"><div class="muted">LIVE CODEX · REAL GITHUB TASK · {accepted}/2 complete · {functional}/2 functional</div>
<h1>{title}</h1><p><a href="{issue}">Issue</a> · <a href="{repo}">Repository</a> · base <code>{html.escape(str(report.get('base_sha','')))}</code></p>
<p>Model: <code>{html.escape(str(report.get('model','')))}</code> · effort: <code>{html.escape(str(report.get('effort','')))}</code> · execution order: <code>{html.escape(str(report.get('order','')))}</code></p></div>
<div class="cards">
<div class="card"><small>Input delta</small><strong>{_pct(metrics.get('input_token_change_pct'))}</strong></div>
<div class="card"><small>Output delta</small><strong>{_pct(metrics.get('output_token_change_pct'))}</strong></div>
<div class="card"><small>Cost delta</small><strong>{_pct(metrics.get('cost_change_pct'))}</strong></div>
<div class="card"><small>Speedup</small><strong>{_fmt(metrics.get('speedup_factor'))}x</strong></div>
<div class="card"><small>Tool-call delta</small><strong>{_pct(metrics.get('tool_call_change_pct'))}</strong></div>
<div class="card"><small>Complete</small><strong>{_fmt(completed)}/2</strong></div>
<div class="card"><small>Functional</small><strong>{_fmt(functional)}/2</strong></div>
</div>
<section class="panel"><h2>Absolute telemetry</h2><div class="legend"><span><i class="dot base"></i>Baseline</span><span><i class="dot ultra"></i>Astra-Ultra</span></div>{chart}</section>
<section class="panel"><h2>Raw metrics</h2><table><thead><tr><th>Metric</th><th class="base">Baseline</th><th class="ultra">Astra-Ultra</th></tr></thead><tbody>{table}</tbody></table><p class="muted">Reasoning tokens are a subset of output tokens and are not added again for billing. Missing terminal telemetry is shown as n/a, never as zero-cost success.</p></section>
<section class="panel"><h2>Correctness gate</h2><table><thead><tr><th>Criterion</th><th class="base">Baseline</th><th class="ultra">Astra-Ultra</th></tr></thead><tbody>{criteria_rows}</tbody></table></section>
<section class="panel"><h2>Artifacts</h2><p class="muted">The JSON report contains exact event, prompt, answer, test, acceptance and diff paths under the benchmark artifact directory. Worktrees are detached from the same base commit and intentionally preserved for inspection.</p></section>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--html", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8-sig"))
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(report), encoding="utf-8")
    print(args.html.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
