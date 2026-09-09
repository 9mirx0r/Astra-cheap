"""Build a reproducible three-arm report for the real GitHub task benchmark."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


VARIANTS = ("baseline", "astra-ultra", "lattice")
LABELS = {"baseline": "Baseline", "astra-ultra": "Astra Ultra", "lattice": "Lattice"}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return html.escape(str(value))


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):+.2f}%"


def _load_attempts(root: Path, slug: str, official: Path) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for path in sorted(root.glob(f"*-{slug}/real_task_results.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in report.get("results", []):
            if item.get("variant") != "lattice":
                continue
            attempts.append(
                {
                    "artifact": path.parent.name,
                    "path": str(path.resolve()),
                    "official": path.resolve() == official.resolve(),
                    "status": item.get("status"),
                    "internal_status": item.get("internal_status"),
                    "accepted": item.get("accepted"),
                    "agent_success": item.get("agent_success"),
                    "elapsed_seconds": item.get("elapsed_seconds"),
                    "input_tokens": item.get("usage", {}).get("input_tokens"),
                    "page_faults": item.get("lattice_telemetry", {}).get("pageFaults"),
                    "worker_turns": item.get("lattice_telemetry", {}).get("workerTurns"),
                    "failure_reasons": item.get("failure_reasons", []),
                }
            )
    return attempts


def _normalized(report: dict[str, Any]) -> dict[str, Any]:
    results = {item.get("variant"): item for item in report.get("results", [])}
    normalized: dict[str, Any] = {}
    for variant in VARIANTS:
        item = results.get(variant, {})
        success = item.get("agent_success")
        if success is None:
            success = bool(item.get("returncode") == 0 and item.get("status") in {"completed", "accepted"})
        normalized[variant] = {**item, "agent_success": success}
    return normalized


def _data(report: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    results = _normalized(report)
    totals = report.get("totals", {})
    metrics: dict[str, Any] = {}
    for variant in VARIANTS:
        result = results[variant]
        total = totals.get(variant, {})
        usage = result.get("usage", {})
        telemetry = result.get("lattice_telemetry", {})
        runtime_telemetry = result.get("runtime_telemetry", {})
        if variant == "astra-ultra" and runtime_telemetry:
            page_faults = runtime_telemetry.get("page_faults")
            loaded_pages = next(
                (
                    event.get("page_count")
                    for event in runtime_telemetry.get("events", [])
                    if event.get("event") == "context_ready"
                ),
                None,
            )
            initial_context_tokens = next(
                (
                    event.get("estimated_tokens")
                    for event in runtime_telemetry.get("events", [])
                    if event.get("event") == "context_ready"
                ),
                None,
            )
            worker_turns = runtime_telemetry.get("turns")
        else:
            page_faults = telemetry.get("pageFaults")
            loaded_pages = telemetry.get("loadedPageCount")
            initial_context_tokens = telemetry.get("initialContextEstimatedTokens")
            worker_turns = telemetry.get("workerTurns")
        metrics[variant] = {
            "input": usage.get("input_tokens", total.get("input_tokens")),
            "cached": usage.get("cached_input_tokens", total.get("cached_input_tokens")),
            "fresh": (
                usage.get("input_tokens", total.get("input_tokens", 0))
                - usage.get("cached_input_tokens", total.get("cached_input_tokens", 0))
                if isinstance(usage.get("input_tokens", total.get("input_tokens")), (int, float))
                and isinstance(usage.get("cached_input_tokens", total.get("cached_input_tokens")), (int, float))
                else None
            ),
            "output": usage.get("output_tokens", total.get("output_tokens")),
            "reasoning": usage.get("reasoning_output_tokens", total.get("reasoning_output_tokens")),
            "cost": result.get("estimated_cost_usd", total.get("estimated_cost_usd")),
            "elapsed": result.get("elapsed_seconds", total.get("elapsed_seconds")),
            "tests_elapsed": result.get("tests", {}).get("elapsed_seconds", total.get("test_elapsed_seconds")),
            "acceptance_elapsed": result.get("external_acceptance", {}).get(
                "elapsed_seconds", total.get("acceptance_elapsed_seconds")
            ),
            "events": result.get("observed", {}).get("event_count", total.get("event_count")),
            "turns": result.get("observed", {}).get("turn_count", total.get("turn_count")),
            "tool_calls": result.get("observed", {}).get("tool_call_count", total.get("tool_call_count")),
            "files": result.get("diff", {}).get("changed_file_count", total.get("changed_file_count")),
            "added": result.get("diff", {}).get("lines_added", total.get("lines_added")),
            "deleted": result.get("diff", {}).get("lines_deleted", total.get("lines_deleted")),
            "page_faults": page_faults,
            "recovery_attempts": runtime_telemetry.get("recovery_attempts") if runtime_telemetry else None,
            "loaded_pages": loaded_pages,
            "initial_context_tokens": initial_context_tokens,
            "worker_turns": worker_turns,
            "protocol_repairs": telemetry.get("protocolRepairTurns"),
        }
    return {
        "meta": {
            "title": report.get("issue_title", "Real GitHub task"),
            "repository": report.get("repository"),
            "issue": report.get("issue"),
            "base_sha": report.get("base_sha"),
            "model": report.get("model"),
            "effort": report.get("effort"),
            "execution_mode": report.get("execution_mode"),
            "artifact_dir": report.get("artifact_dir"),
        },
        "metrics": metrics,
        "comparisons": report.get("metrics", {}).get("comparison_vs_baseline", {}),
        "results": {
            variant: {
                "status": item.get("status"),
                "internal_status": item.get("internal_status"),
                "agent_success": item.get("agent_success"),
                "accepted": item.get("accepted"),
                "functional_acceptance": item.get("functional_acceptance"),
                "implementation_complete": item.get("implementation_complete"),
                "tests_green": item.get("tests", {}).get("returncode") == 0,
                "acceptance_green": item.get("external_acceptance", {}).get("returncode") == 0,
                "test_count": (
                    int(match.group(1))
                    if (match := re.search(r"(\d+)\s+passed", item.get("tests", {}).get("output_preview") or ""))
                    else None
                ),
                "changed_files": item.get("diff", {}).get("changed_files", []),
                "failure_reasons": item.get("failure_reasons", []),
            }
            for variant, item in _normalized(report).items()
        },
        "attempts": attempts,
    }


def _body(data: dict[str, Any]) -> str:
    meta = data["meta"]
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    title = html.escape(str(meta["title"]))
    total_variants = len(data["metrics"])
    accepted_variants = sum(1 for item in data["results"].values() if item.get("accepted"))
    functional_variants = sum(1 for item in data["results"].values() if item.get("functional_acceptance"))
    return f"""
<main id="three-arm-benchmark" aria-labelledby="benchmark-title">
  <header class="hero">
    <p class="eyebrow">LIVE CODEX · REAL GITHUB TASK · THREE ARM</p>
    <h1 id="benchmark-title">{title}</h1>
    <p class="meta-line"><a href="{html.escape(str(meta['issue']))}">Issue</a> · <a href="{html.escape(str(meta['repository']))}">repository</a> · base <code>{html.escape(str(meta['base_sha']))}</code></p>
    <p class="meta-line">{html.escape(str(meta['model']))} · effort {html.escape(str(meta['effort']))} · execution {html.escape(str(meta['execution_mode']))}</p>
    <div class="outcome" aria-live="polite"><strong>{accepted_variants}/{total_variants} accepted</strong><span>{functional_variants}/{total_variants} functional</span><span>same base SHA</span><span>paired + validated retry</span></div>
  </header>

  <section aria-labelledby="tokens-title">
    <h2 id="tokens-title">Raw token telemetry</h2>
    <div class="chart-wrap"><div id="token-chart" class="chart" role="img" aria-label="Grouped bars comparing raw token counts"></div></div>
  </section>

  <section aria-labelledby="runtime-title">
    <h2 id="runtime-title">Runtime, cost and footprint</h2>
    <div class="chart-wrap"><div id="runtime-chart" class="chart" role="img" aria-label="Grouped bars comparing runtime and cost"></div></div>
  </section>

  <section aria-labelledby="comparison-title">
    <h2 id="comparison-title">Change versus baseline</h2>
    <div class="chart-wrap"><div id="delta-chart" class="chart" role="img" aria-label="Percent change versus baseline"></div></div>
  </section>

  <section aria-labelledby="raw-title">
    <h2 id="raw-title">Exact values</h2>
    <div class="table-responsive"><table><thead><tr><th>Metric</th><th>Baseline</th><th>Astra Ultra</th><th>Lattice</th></tr></thead><tbody id="raw-table"></tbody></table></div>
    <p class="note">Input includes cached input; fresh input is input minus cached. Reasoning output is a subset of output tokens. Lattice tool calls are not emitted by its own runtime and remain n/a.</p>
  </section>

  <section aria-labelledby="gate-title">
    <h2 id="gate-title">Correctness gate</h2>
    <div class="table-responsive"><table><thead><tr><th>Criterion</th><th>Baseline</th><th>Astra Ultra</th><th>Lattice</th></tr></thead><tbody id="gate-table"></tbody></table></div>
  </section>

  <section aria-labelledby="history-title">
    <h2 id="history-title">Lattice robustness history</h2>
    <p class="note">Previous attempts are retained to show which failures were fixed; only the official three-arm run is used for the comparison above.</p>
    <div class="table-responsive"><table><thead><tr><th>Attempt</th><th>Internal</th><th>Accepted</th><th>Elapsed</th><th>Input</th><th>Faults</th><th>Failure</th></tr></thead><tbody id="history-table"></tbody></table></div>
  </section>
</main>
<script>
(() => {{
  const data = {payload};
  const order = ['baseline', 'astra-ultra', 'lattice'];
  const labels = {{baseline: 'Baseline', 'astra-ultra': 'Astra Ultra', lattice: 'Lattice'}};
  const colors = {{baseline: 'var(--viz-series-1)', 'astra-ultra': 'var(--viz-series-2)', lattice: 'var(--viz-series-3)'}};
  const nf = new Intl.NumberFormat('en-US');
  const money = value => value == null ? 'n/a' : '$' + Number(value).toFixed(5);
  const value = (key, variant) => data.metrics[variant][key];
  const format = (key, raw) => {{
    if (raw == null) return 'n/a';
    if (key === 'cost') return money(raw);
    if (key.endsWith('elapsed') || key === 'elapsed') return Number(raw).toFixed(2) + ' s';
    return nf.format(Math.round(raw));
  }};
  const esc = text => String(text).replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));

  function drawBars(id, title, rows) {{
    const host = document.getElementById(id);
    const width = Math.max(320, host.clientWidth || 736);
    const left = width < 520 ? 128 : 178;
    const right = 92;
    const rowHeight = 58;
    const height = rows.length * rowHeight + 38;
    const allValues = rows.flatMap(row => order.map(variant => Number(row.values[variant]) || 0));
    const diverging = Math.min(...allValues) < 0 && Math.max(...allValues) > 0;
    const min = diverging ? Math.min(0, ...allValues) : 0;
    const max = diverging ? Math.max(0, ...allValues) : Math.max(1, ...allValues);
    const domain = Math.max(1, max - min);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
    svg.setAttribute('class', 'bar-svg');
    svg.setAttribute('role', 'img');
    const titleNode = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    titleNode.textContent = title;
    svg.appendChild(titleNode);
    const axis = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    axis.setAttribute('class', 'axis-title'); axis.setAttribute('data-axis', 'x');
    axis.setAttribute('x', left); axis.setAttribute('y', height - 4); axis.textContent = rows[0].axisLabel || 'absolute value'; svg.appendChild(axis);
    if (diverging) {{
      const zero = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      const zeroX = left + (-min / domain) * (width - left - right);
      zero.setAttribute('x1', zeroX); zero.setAttribute('x2', zeroX); zero.setAttribute('y1', 0); zero.setAttribute('y2', height - 14); zero.setAttribute('stroke', 'var(--border)'); zero.setAttribute('stroke-width', '1'); svg.appendChild(zero);
    }}
    rows.forEach((row, index) => {{
      const y = index * rowHeight + 8;
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('class', 'row-label'); label.setAttribute('x', 0); label.setAttribute('y', y + 16); label.textContent = row.label; svg.appendChild(label);
      order.forEach((variant, series) => {{
        const raw = row.values[variant];
        const barY = y + series * 14;
        const bar = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const zeroX = left + (-min / domain) * (width - left - right);
        const barWidth = raw == null ? 0 : Math.max(1, Math.abs(Number(raw)) / domain * (width - left - right));
        bar.setAttribute('x', diverging && raw != null && Number(raw) < 0 ? zeroX - barWidth : diverging ? zeroX : left); bar.setAttribute('y', barY); bar.setAttribute('height', 10);
        bar.setAttribute('width', barWidth);
        bar.setAttribute('fill', colors[variant]); bar.setAttribute('rx', 2);
        bar.setAttribute('data-tooltip', `${{labels[variant]}} · ${{row.label}}: ${{row.format ? row.format(raw) : format(row.key, raw)}}`);
        svg.appendChild(bar);
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('class', 'bar-value'); text.setAttribute('x', width - right + 6); text.setAttribute('y', barY + 9); text.textContent = raw == null ? 'n/a' : (row.format ? row.format(raw) : format(row.key, raw)); svg.appendChild(text);
      }});
    }});
    host.replaceChildren(svg);
  }}

  const tokenRows = [
    {{key:'input', label:'Input', values:{{}}}}, {{key:'cached', label:'Cached input', values:{{}}}},
    {{key:'fresh', label:'Fresh input', values:{{}}}}, {{key:'output', label:'Output', values:{{}}}},
    {{key:'reasoning', label:'Reasoning output', values:{{}}}}
  ];
  const runtimeRows = [
    {{key:'elapsed', label:'Agent wall time', values:{{}}}}, {{key:'tests_elapsed', label:'Target tests', values:{{}}}},
    {{key:'acceptance_elapsed', label:'External acceptance', values:{{}}}}, {{key:'cost', label:'Estimated cost', values:{{}}, format: money}},
    {{key:'files', label:'Files changed', values:{{}}}}, {{key:'added', label:'Lines added', values:{{}}}}
  ];
  [...tokenRows, ...runtimeRows].forEach(row => order.forEach(variant => row.values[variant] = value(row.key, variant)));
  drawBars('token-chart', 'Raw token counts', tokenRows);
  drawBars('runtime-chart', 'Runtime, cost and diff footprint', runtimeRows);

  const comparisonRows = [
    ['input_token_change_pct', 'Input tokens'], ['cached_input_change_pct', 'Cached input'],
    ['output_token_change_pct', 'Output tokens'], ['reasoning_token_change_pct', 'Reasoning'],
    ['latency_change_pct', 'Agent wall time'], ['test_latency_change_pct', 'Target tests'],
    ['cost_change_pct', 'Estimated cost'], ['tool_call_change_pct', 'Tool calls']
  ];
  const deltaRows = comparisonRows.map(([key, label]) => {{
    const row = {{key, label, axisLabel: 'change vs baseline (%)', values: {{baseline: 0, 'astra-ultra': data.comparisons['astra-ultra']?.[key], lattice: data.comparisons.lattice?.[key]}}, format: raw => raw == null ? 'n/a' : Number(raw).toFixed(2) + '%'}};
    return row;
  }});
  drawBars('delta-chart', 'Percent change versus baseline', deltaRows);

  const rawRows = [
    ['input','Input tokens'], ['cached','Cached input'], ['fresh','Fresh input'], ['output','Output tokens'], ['reasoning','Reasoning output'],
    ['cost','Estimated cost'], ['elapsed','Agent wall time'], ['tests_elapsed','Target test time'], ['acceptance_elapsed','Acceptance time'],
    ['events','JSONL/events'], ['turns','Worker/model turns'], ['tool_calls','Tool calls'], ['page_faults','Context page faults'], ['recovery_attempts','Recovery attempts'], ['loaded_pages','Loaded pages'],
    ['initial_context_tokens','Initial context estimate'], ['files','Files changed'], ['added','Lines added'], ['deleted','Lines deleted']
  ];
  document.getElementById('raw-table').innerHTML = rawRows.map(([key,label]) => `<tr><th>${{esc(label)}}</th>${{order.map(variant => `<td>${{esc(format(key, value(key, variant)))}}</td>`).join('')}}</tr>`).join('');

  const criteria = [
    ['agent_success','Agent completed'], ['implementation_complete','Implementation complete'], ['tests_green','Targeted tests green'],
    ['acceptance_green','External acceptance green'], ['functional_acceptance','Functional acceptance'], ['changed_files','Changed files']
  ];
  document.getElementById('gate-table').innerHTML = criteria.map(([key,label]) => `<tr><th>${{esc(label)}}</th>${{order.map(variant => {{ const item=data.results[variant]; const raw=item[key]; const pass=key==='changed_files' ? raw.length + ' files' : (raw ? 'PASS' : 'FAIL'); return `<td class="${{raw ? 'pass' : 'fail'}}">${{esc(pass)}}</td>`; }}).join('')}}</tr>`).join('');

  const attempts = [...data.attempts].reverse();
  document.getElementById('history-table').innerHTML = attempts.map(item => `<tr class="${{item.official ? 'official' : ''}}"><th>${{esc(item.artifact)}}${{item.official ? ' · official' : ''}}</th><td>${{esc(item.internal_status || item.status || 'n/a')}}</td><td class="${{item.accepted ? 'pass' : 'fail'}}">${{item.accepted ? 'PASS' : 'FAIL'}}</td><td>${{item.elapsed_seconds == null ? 'n/a' : Number(item.elapsed_seconds).toFixed(1) + ' s'}}</td><td>${{item.input_tokens == null ? 'n/a' : nf.format(item.input_tokens)}}</td><td>${{item.page_faults == null ? 'n/a' : item.page_faults}}</td><td>${{esc((item.failure_reasons || []).join(', ') || '—')}}</td></tr>`).join('');

  const redraw = () => {{ drawBars('token-chart','Raw token counts',tokenRows); drawBars('runtime-chart','Runtime, cost and diff footprint',runtimeRows); drawBars('delta-chart','Percent change versus baseline',deltaRows); }};
  new ResizeObserver(redraw).observe(document.getElementById('three-arm-benchmark'));
}})();
</script>
"""


def _style() -> str:
    return """
<style>
:root { color-scheme: light dark; --background: light-dark(#f8fafc,#0b1020); --foreground: light-dark(#172033,#e8eefc); --muted-foreground: light-dark(#5e6b82,#a9b7d0); --border: light-dark(#d9e0eb,#2b3854); --viz-series-1: light-dark(#cf3d61,#fb7185); --viz-series-2: light-dark(#087f69,#34d399); --viz-series-3: light-dark(#1769aa,#7dd3fc); --popover: light-dark(#ffffff,#151f35); --popover-foreground: var(--foreground); }
* { box-sizing: border-box; }
body { margin: 0; background: var(--background); color: var(--foreground); font: 14px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }
main { max-width: 1024px; margin: 0 auto; padding: 28px 20px 56px; }
h1 { margin: 0 0 8px; font-size: clamp(22px, 4vw, 34px); font-weight: 500; line-height: 1.15; }
h2 { margin: 34px 0 10px; font-size: 18px; font-weight: 500; }
.hero { border-bottom: 1px solid var(--border); padding-bottom: 18px; }
.eyebrow { margin: 0 0 8px; color: var(--muted-foreground); font-size: 12px; letter-spacing: .08em; }
.meta-line, .note { color: var(--muted-foreground); margin: 7px 0; }
a { color: var(--viz-series-3); }
code { color: var(--viz-series-3); overflow-wrap: anywhere; }
.outcome { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 16px; color: var(--muted-foreground); }
.outcome strong { color: var(--viz-series-2); font-weight: 500; }
.chart-wrap { width: 100%; }
.chart { min-height: 160px; width: 100%; }
.bar-svg { display: block; width: 100%; height: auto; overflow: visible; }
.bar-svg text { fill: var(--foreground); font-size: 12px; }
.bar-svg .row-label { font-weight: 500; }
.bar-svg .bar-value { fill: var(--muted-foreground); font-variant-numeric: tabular-nums; }
.bar-svg .axis-title { fill: var(--muted-foreground); font-size: 11px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 9px; border-bottom: 1px solid var(--border); text-align: right; vertical-align: top; }
th:first-child, td:first-child { text-align: left; }
thead th { color: var(--muted-foreground); font-size: 12px; font-weight: 500; }
td { font-variant-numeric: tabular-nums; }
.pass { color: var(--viz-series-2); font-weight: 500; }
.fail { color: var(--viz-series-1); font-weight: 500; }
.official { background: color-mix(in srgb, var(--viz-series-3) 9%, transparent); }
.table-responsive { overflow-x: auto; }
@media (max-width: 560px) { main { padding: 22px 12px 44px; } th, td { padding: 7px 5px; font-size: 12px; } .bar-svg text { font-size: 11px; } }
</style>
"""


def build_html(data: dict[str, Any]) -> str:
    return "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Three-arm real task benchmark</title>" + _style() + "</head><body>" + _body(data) + "</body></html>"


def build_fragment(data: dict[str, Any]) -> str:
    return _style() + _body(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--fragment", type=Path)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--attempts-root", type=Path)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8-sig"))
    official = args.input.resolve()
    attempts_root = (args.attempts_root or args.input.parent.parent).resolve()
    data = _data(report, _load_attempts(attempts_root, report.get("task_slug", ""), official))
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(data), encoding="utf-8")
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.fragment:
        args.fragment.parent.mkdir(parents=True, exist_ok=True)
        args.fragment.write_text(build_fragment(data), encoding="utf-8")
    print(args.html.resolve())
    if args.fragment:
        print(args.fragment.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
