#!/usr/bin/env python3
"""Astra-Ultra Universal Reasoning Governor & Circuit Breaker for OpenAI Codex.

Supports ALL models (GPT-4o, o1, o3-mini, o3, Luna 5.6, Terra) across ANY reasoning effort:
  - Effort levels: 'none', 'low', 'medium', 'high', 'max', 'xhigh'
  - High/Max Effort Optimization: When models like Luna 5.6 operate at high effort,
    internal chain-of-thought consumes 20,000-50,000+ output tokens per turn.
    Astra-Ultra enforces strict Observation Masking and Surgical Bounded Slicing
    so that intense test-time compute is spent strictly on causal solutions, not noise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EFFORT_TIERS = {"none", "low", "medium", "high", "max", "xhigh"}


def validate_effort(effort: str) -> str:
    eff = effort.strip().lower()
    return eff if eff in EFFORT_TIERS else "high"


class CircuitBreaker:
    """Universal circuit breaker preventing recovery loops across all models and effort tiers."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.state_file.is_file():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8-sig"))
            except Exception:
                pass
        return {"recovery_counts": {}, "tripped": []}

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def register_recovery(self, source_hash: str) -> Tuple[bool, str]:
        counts = self.state.setdefault("recovery_counts", {})
        curr = counts.get(source_hash, 0) + 1
        counts[source_hash] = curr
        self._save()

        if curr >= 2:
            if source_hash not in self.state["tripped"]:
                self.state["tripped"].append(source_hash)
                self._save()
            return False, (
                f"CIRCUIT BREAKER TRIPPED for hash {source_hash[:8]}: "
                f"2 consecutive recovery attempts failed to resolve context. "
                f"HALT REPACKING IMMEDIATELY. To protect quota on high-effort reasoning, "
                f"switch to targeted 'view_file' on exact line numbers."
            )

        return True, f"Recovery attempt {curr}/2 recorded for hash {source_hash[:8]}."


ASYMMETRIC_PROTOCOL: Dict[str, Any] = {
    "protocol_name": "Astra-Ultra Asymmetric 1-Turn Protocol",
    "rationale": (
        "Prevents multi-turn reasoning token exhaustion in high-effort models (e.g. Luna 5.6 High, o1, o3-mini). "
        "High-effort models consume 20,000-50,000+ internal reasoning tokens per turn. Using them for file searching, "
        "directory navigation, or raw log reading quickly exhausts the 5-hour quota. Astra-Ultra splits execution into "
        "two distinct computational tiers: deterministic low-cost reconnaissance followed by a single surgical high-effort synthesis turn."
    ),
    "phases": {
        "phase_1_reconnaissance": {
            "tier": "Tier-0/1 Worker (Terra Medium, GPT-4o-mini, Flash, or deterministic tools)",
            "allowed_tools": ["astra_ast", "astra_repomap", "grep_search", "view_file (bounded <= 50 lines)", "astra_sanitizer"],
            "strictly_forbidden": [
                "Raw file dumping (>100 lines)",
                "Unmasked test runner stdout",
                "Invoking High/Max reasoning effort for search or exploration"
            ],
            "deliverable": "Surgical context packet: exact file path, bounded lines [N-M] (<=50 lines), sanitized error traceback."
        },
        "phase_2_synthesis": {
            "tier": "Tier-3 High-Reasoning Engine (Luna 5.6 High/Max, o1, o3)",
            "turn_budget": 1,
            "input_payload": "Surgical packet from Phase 1 + AST skeleton + exact concurrency/mathematical invariant specification.",
            "execution": "Pure cognitive reasoning on the isolated causal core in a SINGLE turn.",
            "deliverable": "Exact, unified diff patch (no conversational boilerplate)."
        },
        "phase_3_verification": {
            "tier": "Deterministic Test Interceptor",
            "allowed_tools": ["astra_sanitizer wrapped pytest/unittest", "git diff"],
            "circuit_breaker": "Permits at most 1 targeted repair if verification fails, then halts."
        }
    }
}


def get_effort_guidance(model_name: str, effort_level: str) -> Dict[str, Any]:
    """Provides dynamic architectural guidance for any model and effort setting."""
    effort = validate_effort(effort_level)
    is_high_effort = effort in {"high", "max", "xhigh"}

    guidance: Dict[str, Any] = {
        "model": model_name,
        "effective_effort": effort,
        "high_effort_active": is_high_effort,
        "directives": [
            "Hardware-Invariant Prefix Locking: keep system headers and static skills frozen at byte 0.",
            "AST Skeletons: inspect module topologies with '...' elided bodies before requesting code.",
            "Bounded Window Reading: maximum 50-100 lines with 2-line overlap.",
            "Observation Masking: mask historic command stdout after patch verification."
        ]
    }

    if is_high_effort or "luna" in model_name.lower():
        guidance["high_effort_safeguards"] = [
            "Reasoning Token Defense: Chain-of-thought is active. Do not inject raw test dumps or whole files.",
            "Zero Conversational Filler: deliver code modifications first to terminate generation early.",
            "Deterministic 2-Recovery Limit: stop packing if evidence is missing; read line range directly.",
            "Asymmetric 1-Turn Protocol Active: Luna 5.6 High must only be invoked for single-turn invariant resolution after deterministic recon."
        ]
        guidance["asymmetric_protocol"] = ASYMMETRIC_PROTOCOL

    return guidance


def main() -> int:
    parser = argparse.ArgumentParser(description="Astra-Ultra Universal Reasoning Governor")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    guide_p = subparsers.add_parser("guidance", help="Get execution guidance for any model & effort")
    guide_p.add_argument("--model", default="Luna-5.6", help="Model name (e.g. Luna-5.6, Terra, o3-mini, o1)")
    guide_p.add_argument("--effort", default="high", help="Effort tier: none, low, medium, high, max, xhigh")

    cb_p = subparsers.add_parser("circuit-breaker", help="Check circuit breaker for source hash")
    cb_p.add_argument("--state-file", default=".local/circuit_breaker.json")
    cb_p.add_argument("--source-hash", required=True)

    subparsers.add_parser("asymmetric", help="Display formal Asymmetric 1-Turn Protocol for Luna 5.6 High")

    args = parser.parse_args()

    if args.subcommand == "guidance":
        res = get_effort_guidance(args.model, args.effort)
        print(json.dumps(res, indent=2))
    elif args.subcommand == "circuit-breaker":
        cb = CircuitBreaker(Path(args.state_file))
        allowed, msg = cb.register_recovery(args.source_hash)
        print(json.dumps({"allowed": allowed, "message": msg}, indent=2))
        return 0 if allowed else 1
    elif args.subcommand == "asymmetric":
        print(json.dumps(ASYMMETRIC_PROTOCOL, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
