"""Build an aggregate report and dashboard from live benchmark ledgers."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def load_ledgers(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    ledgers = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        results = data.get("results", [])
        if len(results) != 2 or {row.get("variant") for row in results} != {"baseline", "astra-ultra"}:
            raise ValueError(f"{path} must contain exactly one baseline and one astra-ultra result")
        if not all(row.get("mode") == "live_codex_execution" for row in results):
            raise ValueError(f"{path} is not a live Codex ledger")
        if not all(row.get("accepted") is True for row in results):
            raise ValueError(f"{path} contains a non-accepted result")
        ledgers.append(data)
    return ledgers


def aggregate(ledgers: List[Dict[str, Any]], source_files: Iterable[Path] = ()) -> Dict[str, Any]:
    totals: Dict[str, Dict[str, float]] = {
        variant: {field: 0 for field in FIELDS} | {
            "elapsed_seconds": 0,
            "estimated_cost_usd": 0,
            "event_count": 0,
            "turn_count": 0,
            "tool_call_count": 0,
        }
        for variant in ("baseline", "astra-ultra")
    }
    workloads = []

    for ledger in ledgers:
        rows = {row["variant"]: row for row in ledger["results"]}
        workload_row = {
            "workload_id": ledger.get("workload_id"),
            "workload_name": ledger.get("workload_name"),
            "baseline": rows["baseline"],
            "astra_ultra": rows["astra-ultra"],
        }
        workloads.append(workload_row)
        for variant, row in rows.items():
            usage = row.get("usage", {}) or {}
            for field in FIELDS:
                totals[variant][field] += usage.get(field, 0) or 0
            totals[variant]["elapsed_seconds"] += row.get("elapsed_seconds", 0) or 0
            totals[variant]["estimated_cost_usd"] += row.get("estimated_cost_usd", 0) or 0
            observed = row.get("observed", {}) or {}
            for field in ("event_count", "turn_count", "tool_call_count"):
                totals[variant][field] += observed.get(field, 0) or 0

    base = totals["baseline"]
    ultra = totals["astra-ultra"]
    # Codex reports reasoning_output_tokens as a subset of output_tokens.
    # Never add it again when calculating billed/output volume.
    base_total_out = base["output_tokens"]
    ultra_total_out = ultra["output_tokens"]
    input_savings = ((base["input_tokens"] - ultra["input_tokens"]) / base["input_tokens"] * 100)
    cost_savings = ((base["estimated_cost_usd"] - ultra["estimated_cost_usd"]) / base["estimated_cost_usd"] * 100)
    latency_change = ((ultra["elapsed_seconds"] - base["elapsed_seconds"]) / base["elapsed_seconds"] * 100)

    return {
        "model": ledgers[0].get("model"),
        "effort": ledgers[0].get("effort"),
        "source_files": [str(path) for path in source_files],
        "workloads": workloads,
        "totals": totals,
        "metrics": {
            "input_token_savings_pct": round(input_savings, 2),
            "ultra_cache_hit_pct": round(ultra["cached_input_tokens"] / ultra["input_tokens"] * 100, 2),
            "output_token_change_pct": round((ultra_total_out - base_total_out) / base_total_out * 100, 2),
            "latency_change_pct": round(latency_change, 2),
            "speedup_factor": round(base["elapsed_seconds"] / ultra["elapsed_seconds"], 3),
            "estimated_cost_savings_pct": round(cost_savings, 2),
            "cache_write_delta_pct": round(
                ((ultra["cache_write_input_tokens"] - base["cache_write_input_tokens"])
                 / max(base["cache_write_input_tokens"], 1) * 100),
                2,
            ),
            "tool_call_delta_pct": round(
                ((ultra["tool_call_count"] - base["tool_call_count"])
                 / max(base["tool_call_count"], 1) * 100),
                2,
            ),
            "accepted_workloads": sum(
                int(item["baseline"].get("accepted", False) and item["astra_ultra"].get("accepted", False))
                for item in workloads
            ),
            "workload_count": len(workloads),
        },
    }


def fmt_number(value: float) -> str:
    return f"{value:,.0f}"


def fmt_money(value: float) -> str:
    return f"${value:,.5f}"


def metric_pair(label: str, base: float, ultra: float, unit: str, decimals: int = 0) -> str:
    maximum = max(base, ultra, 1e-9)
    base_width = 100
    ultra_width = ultra / maximum * 100
    if decimals:
        base_text = f"{base:,.{decimals}f} {unit}"
        ultra_text = f"{ultra:,.{decimals}f} {unit}"
    else:
        base_text = f"{fmt_number(base)} {unit}"
        ultra_text = f"{fmt_number(ultra)} {unit}"
    return f"""
      <section class="metric">
        <h2>{html.escape(label)}</h2>
        <div class="row"><span>Baseline</span><strong>{base_text}</strong></div>
        <div class="track"><div class="bar baseline" style="width:{base_width:.1f}%"></div></div>
        <div class="row"><span>Astra-Ultra</span><strong>{ultra_text}</strong></div>
        <div class="track"><div class="bar ultra" style="width:{ultra_width:.1f}%"></div></div>
      </section>
    """


def build_html(report: Dict[str, Any]) -> str:
    totals = report["totals"]
    base = totals["baseline"]
    ultra = totals["astra-ultra"]
    base_total_out = base["output_tokens"]
    ultra_total_out = ultra["output_tokens"]
    metrics = report["metrics"]
    workload_rows = []
    for workload in report["workloads"]:
        b = workload["baseline"]
        u = workload["astra_ultra"]
        b_in = b["usage"]["input_tokens"]
        u_in = u["usage"]["input_tokens"]
        savings = (b_in - u_in) / b_in * 100
        workload_rows.append(
            f"<tr><td>{html.escape(workload['workload_name'])}</td>"
            f"<td>{fmt_number(b_in)}</td><td>{fmt_number(u_in)}</td>"
            f"<td>{savings:+.1f}%</td><td>{b['elapsed_seconds']:.2f}s</td>"
            f"<td>{u['elapsed_seconds']:.2f}s</td><td>{'PASS' if u.get('accepted') else 'FAIL'}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luna 5.6 Astra-Ultra live benchmark suite</title>
<style>
  :root {{ color-scheme: dark; --bg:#0f172a; --surface:#1e293b; --muted:#94a3b8; --line:#334155; --base:#fb7185; --ultra:#34d399; --accent:#38bdf8; }}
  * {{ box-sizing:border-box; }} body {{ margin:0; padding:32px; background:var(--bg); color:#f8fafc; font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  main {{ max-width:1050px; margin:auto; }} h1 {{ margin:0 0 6px; color:var(--accent); }} h2 {{ font-size:15px; margin:0 0 12px; color:var(--muted); }}
  .sub {{ color:var(--muted); margin:0 0 26px; }} .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:24px; }}
  .metric {{ padding:18px 0; border-top:1px solid var(--line); }} .row {{ display:flex; justify-content:space-between; gap:16px; margin-top:9px; }}
  .row strong {{ font-variant-numeric:tabular-nums; }} .track {{ height:18px; background:var(--line); margin-top:4px; overflow:hidden; }} .bar {{ height:100%; }} .baseline {{ background:var(--base); }} .ultra {{ background:var(--ultra); }}
  .summary {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin:26px 0 18px; }} .summary div {{ border-left:3px solid var(--accent); padding:10px 12px; background:var(--surface); }}
  .summary b {{ display:block; font-size:23px; font-variant-numeric:tabular-nums; }} .summary span {{ color:var(--muted); font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:26px; font-variant-numeric:tabular-nums; }} th,td {{ text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); }} th {{ color:var(--muted); font-weight:500; }}
  @media(max-width:700px) {{ body {{ padding:20px; }} .grid,.summary {{ grid-template-columns:1fr; }} table {{ display:block; overflow-x:auto; white-space:nowrap; }} }}
</style></head><body><main>
<h1>Luna 5.6 · Astra-Ultra live benchmark suite</h1>
<p class="sub">Requested model: {html.escape(str(report['model']))} · effort: {html.escape(str(report['effort']))} · {metrics['accepted_workloads']}/{metrics['workload_count']} workloads accepted</p>
<div class="summary">
  <div><b>{metrics['input_token_savings_pct']:+.1f}%</b><span>input token change</span></div>
  <div><b>{metrics['estimated_cost_savings_pct']:+.1f}%</b><span>estimated cost change</span></div>
  <div><b>{metrics['speedup_factor']:.3f}×</b><span>wall-clock speedup</span></div>
</div>
<div class="grid">
{metric_pair('Total input tokens · lower is better', base['input_tokens'], ultra['input_tokens'], 'tokens')}
{metric_pair('Output tokens · reasoning included', base_total_out, ultra_total_out, 'tokens')}
{metric_pair('Wall-clock execution time · lower is better', base['elapsed_seconds'], ultra['elapsed_seconds'], 'seconds', 2)}
{metric_pair('Estimated cost · lower is better', base['estimated_cost_usd'], ultra['estimated_cost_usd'], 'USD', 5)}
{metric_pair('Observed tool calls · lower is better', base['tool_call_count'], ultra['tool_call_count'], 'calls')}
</div>
<section><h2>Per-workload acceptance and input volume</h2>
<table><thead><tr><th>Workload</th><th>Baseline in</th><th>Astra in</th><th>Delta</th><th>Base time</th><th>Astra time</th><th>Acceptance</th></tr></thead>
<tbody>{''.join(workload_rows)}</tbody></table></section>
<p class="sub">Astra-Ultra cache hit rate: {metrics['ultra_cache_hit_pct']:.2f}% · output token change (reasoning included): {metrics['output_token_change_pct']:+.2f}% · latency change: {metrics['latency_change_pct']:+.2f}% · tool-call change: {metrics['tool_call_delta_pct']:+.2f}%.</p>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--html", required=True)
    args = parser.parse_args()

    global INPUT_PATHS
    INPUT_PATHS = [Path(item) for item in args.inputs]
    report = aggregate(load_ledgers(INPUT_PATHS), INPUT_PATHS)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    dashboard = Path(args.html)
    dashboard.parent.mkdir(parents=True, exist_ok=True)
    dashboard.write_text(build_html(report), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Report written to {output.resolve()}")
    print(f"Dashboard written to {dashboard.resolve()}")
    return 0


if __name__ == "__main__":
    INPUT_PATHS: List[Path] = []
    raise SystemExit(main())
