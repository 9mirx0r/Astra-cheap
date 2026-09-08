import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import astra_ast
import astra_repomap
import astra_prefix_lock
import astra_sanitizer
import astra_governor
import astra_mcp_server


class TestAstraAst(unittest.TestCase):
    def test_python_skeleton(self):
        code = """def calculate_total(a: int, b: int) -> int:
    \"\"\"Sum numbers.\"\"\"
    x = a * 2
    return x + b
"""
        skel = astra_ast.python_skeleton(code)
        self.assertIn("def calculate_total(a: int, b: int) -> int:", skel)
        self.assertIn('"""Sum numbers."""', skel)
        self.assertIn("...", skel)
        self.assertNotIn("x = a * 2", skel)

    def test_python_symbols(self):
        code = "class Calculator:\n    def add(self, x):\n        pass\n"
        symbols = astra_ast.python_symbols(code)
        names = [s["name"] for s in symbols]
        self.assertIn("Calculator", names)
        self.assertIn("add", names)

    def test_js_ts_skeleton(self):
        code = "export function processData(items: any[]): void {\n  console.log(items);\n}\n"
        skel = astra_ast.js_ts_skeleton(code)
        self.assertIn("export function processData(items: any[]): void {", skel)
        self.assertIn("...", skel)
        self.assertNotIn("console.log", skel)


class TestAstraRepoMap(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        (Path(self.test_dir) / "alpha.py").write_text("class Alpha:\n    def run(self):\n        pass\n", encoding="utf-8")
        (Path(self.test_dir) / "beta.py").write_text("from alpha import Alpha\na = Alpha()\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_repomap_pagerank_and_budget(self):
        graph = astra_repomap.RepoMapGraph(Path(self.test_dir))
        graph.scan()
        ranks = graph.calculate_pagerank()
        self.assertTrue(len(ranks) > 0)
        repo_map = graph.render_map(budget_tokens=1024)
        self.assertIn("Astra-Ultra RepoMap", repo_map)
        self.assertIn("alpha.py", repo_map)

    def test_subgraph_query(self):
        graph = astra_repomap.RepoMapGraph(Path(self.test_dir))
        graph.scan()
        defs = [d for d in graph.definitions_by_file.get("alpha.py", []) if d["name"] == "Alpha"]
        self.assertEqual(len(defs), 1)


class TestAstraPrefixLock(unittest.TestCase):
    def test_canonicalize_text(self):
        t1 = "line1\r\nline2   \r\n"
        t2 = "line1\nline2\n"
        self.assertEqual(astra_prefix_lock.canonicalize_text(t1), astra_prefix_lock.canonicalize_text(t2))

    def test_merkle_root_determinism(self):
        hashes = ["a" * 64, "b" * 64, "c" * 64]
        r1 = astra_prefix_lock.compute_merkle_root(hashes)
        r2 = astra_prefix_lock.compute_merkle_root(hashes)
        self.assertEqual(r1, r2)

    def test_quantize_prefix_below_min_tokens(self):
        short_text = "System: You are an autonomous coding assistant.\n"
        padded, meta = astra_prefix_lock.quantize_prefix(short_text, boundary=128, min_tokens=1024)
        self.assertGreaterEqual(meta["final_tokens"], 1024)
        self.assertIn("astra-ultra:cache-align", padded)
        self.assertTrue(meta["aligned"])

    def test_quantize_prefix_alignment_128(self):
        # Create text with ~1050 tokens (4200 chars)
        base_text = "# System Directive\n" + ("x = 1\n" * 700)
        curr_tokens = astra_prefix_lock.estimate_tokens(base_text)
        padded, meta = astra_prefix_lock.quantize_prefix(base_text, boundary=128, min_tokens=1024)
        # Should be aligned to 1024 + 128 * k
        final_tok = meta["final_tokens"]
        rem = (final_tok - 1024) % 128
        self.assertEqual(rem, 0)
        self.assertGreaterEqual(final_tok, curr_tokens)


class TestAstraSanitizer(unittest.TestCase):
    def test_cat_large_file_denied(self):
        res = astra_sanitizer.process_command("cat README.md", cwd=str(ROOT))
        self.assertEqual(res.get("decision"), "deny")

    def test_test_runner_wrapped(self):
        res = astra_sanitizer.process_command("pytest tests/test_core.py", cwd=str(ROOT))
        self.assertEqual(res.get("decision"), "allow")
        self.assertIn("overwrite", res)
        self.assertIn("CommandLine", res["overwrite"])

    def test_machine_pipe_preserved(self):
        res = astra_sanitizer.process_command("git status | xargs echo", cwd=str(ROOT))
        self.assertEqual(res.get("decision"), "allow")
        self.assertNotIn("overwrite", res)

    def test_observation_masking(self):
        lines = [f"Log line {i}" for i in range(100)]
        masked = astra_sanitizer.mask_observation("\n".join(lines))
        self.assertIn("masked for context economy", masked)
        self.assertTrue(len(masked.splitlines()) < 30)


class TestAstraGovernor(unittest.TestCase):
    def test_luna_high_guidance(self):
        res = astra_governor.get_effort_guidance("Luna 5.6", "high")
        self.assertEqual(res.get("effective_effort"), "high")
        self.assertTrue(res.get("high_effort_active"))
        self.assertIn("high_effort_safeguards", res)
        self.assertIn("asymmetric_protocol", res)

    def test_asymmetric_protocol_structure(self):
        proto = astra_governor.ASYMMETRIC_PROTOCOL
        self.assertIn("phases", proto)
        phases = proto["phases"]
        self.assertIn("phase_1_reconnaissance", phases)
        self.assertIn("phase_2_synthesis", phases)
        self.assertIn("phase_3_verification", phases)
        self.assertEqual(phases["phase_2_synthesis"]["turn_budget"], 1)

    def test_circuit_breaker(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "cb.json"
            cb = astra_governor.CircuitBreaker(state_file)
            sh = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ok1, _ = cb.register_recovery(sh)
            self.assertTrue(ok1)
            ok2, msg2 = cb.register_recovery(sh)
            self.assertFalse(ok2)
            self.assertIn("CIRCUIT BREAKER TRIPPED", msg2)


class TestAstraMcpServer(unittest.TestCase):
    def test_self_test(self):
        self.assertTrue(astra_mcp_server.run_self_test())

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td) / "workspace"
            ws.mkdir()
            outside = Path(td) / "outside.py"
            outside.write_text("SECRET_KEY = '12345'", encoding="utf-8")

            # 1. Test get_file_skeleton escapes workspace
            res_skel = astra_mcp_server.handle_get_file_skeleton({
                "file_path": str(outside),
                "workspace_root": str(ws)
            })
            self.assertIn("error", res_skel)
            self.assertIn("escapes workspace root", res_skel["error"])

            # 2. Test get_bounded_slice escapes workspace
            res_slice = astra_mcp_server.handle_get_bounded_slice({
                "file_path": str(outside),
                "workspace_root": str(ws)
            })
            self.assertIn("error", res_slice)
            self.assertIn("escapes workspace root", res_slice["error"])

            # 3. Test get_repo_map escapes workspace
            res_map = astra_mcp_server.handle_get_repo_map({
                "root_dir": str(td),
                "workspace_root": str(ws)
            })
            self.assertIn("error", res_map)
            self.assertIn("escapes workspace root", res_map["error"])


if __name__ == "__main__":
    unittest.main()
