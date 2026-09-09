#!/usr/bin/env python3
"""Astra-Ultra Hardware-Invariant Prefix Locking for OpenAI Codex.

Freezes Layer 1 & 2 invariants with SHA-256 Merkle root validation.
Ensures static prefix integrity to maximize cache hit rates on OpenAI's
1,024-token prompt caching boundary with 128-token increments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def canonicalize_text(text: str) -> str:
    """Canonicalizes line endings to LF and strips trailing whitespace."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip() + "\n"


def compute_file_sha256(filepath: Path) -> str:
    """Computes SHA-256 of text with CRLF invariance."""
    try:
        content = filepath.read_text(encoding="utf-8-sig")
        canonical = canonicalize_text(content)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except Exception:
        raw = filepath.read_bytes()
        return hashlib.sha256(raw).hexdigest()


def compute_merkle_root(hashes: List[str]) -> str:
    """Computes a binary Merkle tree root from a list of hex SHA-256 hashes."""
    if not hashes:
        return hashlib.sha256(b"").hexdigest()

    current = sorted(hashes)
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else left
            combined = hashlib.sha256((left + right).encode("utf-8")).hexdigest()
            next_level.append(combined)
        current = next_level

    return current[0]


def build_manifest(root_dir: Path, target_tokens: int = 1024) -> Dict[str, Any]:
    """Scans and locks static invariant files for Codex prompt caching."""
    manifest_files: List[Dict[str, Any]] = []
    file_hashes: List[str] = []

    priority_names = [
        "SKILL.md",
        "agents/openai.yaml",
        "AGENTS.md",
        "GEMINI.md",
        "pyproject.toml"
    ]

    for rel_path in priority_names:
        p = root_dir / rel_path
        if p.is_file():
            f_hash = compute_file_sha256(p)
            file_hashes.append(f_hash)
            manifest_files.append({
                "path": rel_path.replace("\\", "/"),
                "sha256": f_hash,
                "size_bytes": p.stat().st_size
            })

    merkle_root = compute_merkle_root(file_hashes)

    return {
        "manifest_version": 1,
        "target_cache_tokens": target_tokens,
        "merkle_root": merkle_root,
        "files": manifest_files,
        "cache_discipline": "OpenAI 1024-token exact prefix invariant"
    }


def verify_manifest(root_dir: Path, manifest_path: Path) -> Tuple[bool, str]:
    """Verifies that the workspace invariants match the locked manifest."""
    if not manifest_path.is_file():
        return False, f"Manifest not found: {manifest_path}"

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return False, f"Malformed manifest JSON: {exc}"

    expected_files = data.get("files", [])
    current_hashes = []

    for item in expected_files:
        p = root_dir / item["path"]
        if not p.is_file():
            return False, f"Invariant file missing on disk: {item['path']}"
        curr_hash = compute_file_sha256(p)
        if curr_hash != item["sha256"]:
            return False, f"Hash mismatch on {item['path']}: expected {item['sha256'][:8]}, got {curr_hash[:8]}"
        current_hashes.append(curr_hash)

    curr_merkle = compute_merkle_root(current_hashes)
    if curr_merkle != data.get("merkle_root"):
        return False, f"Merkle root mismatch: expected {data.get('merkle_root')[:8]}, computed {curr_merkle[:8]}"

    return True, "Prefix invariants locked and verified (cache-ready)"


def estimate_tokens(text: str) -> int:
    """Standard token approximation (approx 4 chars per token)."""
    if not text:
        return 0
    return (len(text) + 3) // 4


def quantize_prefix(
    prefix_text: str,
    boundary: int = 128,
    min_tokens: int = 1024,
    pad_comment: str = "astra-ultra:cache-align"
) -> Tuple[str, Dict[str, Any]]:
    """Pads static invariant prefix text to align with OpenAI 128-token cache boundaries.

    OpenAI prompt caching caches prefixes in increments of 128 tokens once
    the initial 1,024-token threshold is met. By padding the static prefix
    to a multiple of 128 tokens (at or above min_tokens), downstream dynamic
    messages begin cleanly at a new cache chunk boundary, preventing cache misses
    due to tail fragments.
    """
    canonical = canonicalize_text(prefix_text)
    current_tokens = estimate_tokens(canonical)

    if current_tokens < min_tokens:
        target_tokens = min_tokens
    else:
        remainder = (current_tokens - min_tokens) % boundary
        if remainder == 0:
            target_tokens = current_tokens
        else:
            target_tokens = current_tokens + (boundary - remainder)

    tokens_needed = target_tokens - current_tokens
    if tokens_needed <= 0:
        return canonical, {
            "initial_tokens": current_tokens,
            "target_tokens": current_tokens,
            "padded_tokens": 0,
            "final_tokens": current_tokens,
            "aligned": True
        }

    target_pad_chars = tokens_needed * 4
    header_pad = f"\n# --- {pad_comment} [target: {target_tokens} tokens] ---\n"
    header_chars = len(header_pad)
    remaining_chars = max(0, target_pad_chars - header_chars)

    filler_line = "# " + ("." * 60) + "\n"
    lines_needed = remaining_chars // len(filler_line)
    trailing_rem = remaining_chars % len(filler_line)

    pad_body = filler_line * lines_needed
    if trailing_rem > 2:
        pad_body += "# " + ("." * (trailing_rem - 3)) + "\n"

    padded_text = canonical + header_pad + pad_body
    final_tokens = estimate_tokens(padded_text)

    return padded_text, {
        "initial_tokens": current_tokens,
        "target_tokens": target_tokens,
        "padded_tokens": final_tokens - current_tokens,
        "final_tokens": final_tokens,
        "aligned": True
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Astra-Ultra Hardware-Invariant Prefix Locking")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    build_p = subparsers.add_parser("build", help="Build prefix lock manifest")
    build_p.add_argument("--root", default=".", help="Root directory path")
    build_p.add_argument("--out", default="prefix_lock.json", help="Output manifest path")
    build_p.add_argument("--target-tokens", type=int, default=1024, help="Target token budget")

    verify_p = subparsers.add_parser("verify", help="Verify prefix lock manifest")
    verify_p.add_argument("--root", default=".", help="Root directory path")
    verify_p.add_argument("--manifest", default="prefix_lock.json", help="Manifest path to verify")

    quant_p = subparsers.add_parser("quantize", help="Quantize and pad prefix to 128-token OpenAI cache boundaries")
    quant_p.add_argument("--input", required=True, help="Input file path containing prefix text")
    quant_p.add_argument("--out", default=None, help="Output file path (prints to stdout if omitted)")
    quant_p.add_argument("--boundary", type=int, default=128, help="Cache chunk boundary in tokens (default: 128)")
    quant_p.add_argument("--min-tokens", type=int, default=1024, help="Minimum threshold for cache activation (default: 1024)")

    args = parser.parse_args()
    root_dir = Path(args.root).resolve() if hasattr(args, "root") else Path(".").resolve()

    if args.subcommand == "build":
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = root_dir / out_path
        manifest = build_manifest(root_dir, target_tokens=args.target_tokens)
        out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Prefix lock manifest written to {out_path} (Merkle: {manifest['merkle_root'][:12]}...)")
    elif args.subcommand == "verify":
        man_path = Path(args.manifest)
        if not man_path.is_absolute():
            man_path = root_dir / man_path
        ok, msg = verify_manifest(root_dir, man_path)
        print(f"[{'PASS' if ok else 'FAIL'}] {msg}")
        return 0 if ok else 1
    elif args.subcommand == "quantize":
        inp_path = Path(args.input)
        if not inp_path.is_file():
            print(f"[FAIL] Input file not found: {inp_path}", file=sys.stderr)
            return 1
        raw_text = inp_path.read_text(encoding="utf-8-sig")
        padded, meta = quantize_prefix(raw_text, boundary=args.boundary, min_tokens=args.min_tokens)
        if args.out:
            out_p = Path(args.out)
            out_p.write_text(padded, encoding="utf-8")
            print(f"[OK] Quantized prefix written to {out_p}: {meta['initial_tokens']} -> {meta['final_tokens']} tokens (Aligned to {args.boundary})")
        else:
            print(padded)

    return 0


if __name__ == "__main__":
    sys.exit(main())
