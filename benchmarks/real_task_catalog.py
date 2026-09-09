"""Task definitions for reproducible real-repository agent benchmarks.

The runner keeps the benchmark mechanics generic while each task supplies its
repository checkout, issue contract, bounded source map, host-side acceptance
program, and targeted test command.  Acceptance programs run outside the agent
worktrees, so an agent cannot make the oracle pass by editing the harness.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealTask:
    slug: str
    repository: str
    issue: str
    title: str
    target_directory: str
    statement: str
    test_command: tuple[str, ...]
    evidence_files: tuple[tuple[str, tuple[str, ...]], ...]
    acceptance_code: str
    required_surfaces: tuple[tuple[str, str], ...]
    verification_prefix: tuple[str, ...] = ("uv", "run", "--frozen")
    lattice_verification_command: str | None = None
    astra_context_budget_tokens: int = 24_000
    astra_page_budget_tokens: int = 1_800
    astra_max_page_faults: int = 4
    astra_max_turns: int = 6
    astra_max_recoveries: int = 3


PYDANTIC_REVIEW_REPOSITORY = "https://github.com/pydantic/pydantic-ai.git"
PYDANTIC_REVIEW_ISSUE = "https://github.com/pydantic/pydantic-ai/issues/4723"
PYDANTIC_REVIEW_TITLE = "New end_strategy='review' — let the model review and patch output before finalizing"
PYDANTIC_REVIEW_SLUG = "pydantic-ai-4723-review-output"
PYDANTIC_REVIEW_TEST_COMMAND = (
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
)
PYDANTIC_REVIEW_STATEMENT = f"""# Real GitHub task

- Repository: {PYDANTIC_REVIEW_REPOSITORY}
- Issue: {PYDANTIC_REVIEW_ISSUE}
- Title: {PYDANTIC_REVIEW_TITLE}

## Problem

Pydantic AI's output tool is terminal today: once `final_result` validates, the
run ends and the model cannot inspect or correct its own structured extraction.
This is a problem for forms, invoices and other extraction tasks where a schema
can validate while a field is still semantically wrong.

## Requested behavior

Add an opt-in `end_strategy='review'` mode.  When an output tool produces a
valid result, the framework should store it and return the serialized result to
the model as a non-terminal tool result.  The model must be able to either:

1. call an automatically generated JSON Patch RFC 6902 tool to apply a targeted
   patch to the stored result; the patched value must be revalidated and the
   updated value returned to the model; and
2. call a confirmation tool (the exact public name may follow project
   conventions) to finalize the validated current result.

Invalid output should retain the existing retry behavior. Existing strategies
(`early`, `graceful`, and `exhaustive`) must keep their behavior and the new
mode must remain opt-in and type-safe.

## Acceptance contract

- `Agent(..., end_strategy='review')` is accepted without changing the default.
- A valid output does not terminate the first model turn in review mode.
- A review-only flow can confirm a valid result and returns it to the caller.
- A patch flow can replace a nested scalar using an RFC 6902 operation, then
  confirm and return the patched, revalidated output.
- Invalid patches or invalid final output are rejected through the framework's
  existing retry/error path.
- Relevant tests and documentation are added, and the existing agent/output
  test suites remain green.

## Shared implementation plan

Use this order for both benchmark variants so the baseline is not forced to
rediscover the acceptance path from scratch:

1. Extend the public/type surface for the opt-in strategy while preserving all
   existing strategies.
2. Trace the final-output path through the agent graph and tool execution layer.
3. Implement the review state and generated confirmation/JSON-Patch tools at
   the narrowest existing output-tool seam.
4. Revalidate patched output through the existing output processor before
   returning it to the model.
5. Add focused confirm, patch, invalid-patch, regression, and documentation
   coverage; then run the targeted suite.

Prioritize a working vertical slice early. Do not spend the entire budget on
repository archaeology or broad refactoring.

Do not commit or push. Work only in the provided detached worktree.
"""
PYDANTIC_REVIEW_EVIDENCE_FILES = (
    ("AGENTS.md", ("Requirements of all contributions", "Development workflow", "Pydantic AI is meant")),
    ("pydantic_ai_slim/pydantic_ai/AGENTS.md", ("API Design", "Type System", "Testing")),
    ("tests/AGENTS.md", ("Testing", "Snapshot", "pytest")),
    (
        "pydantic_ai_slim/pydantic_ai/_agent_graph.py",
        ("EndStrategy", "def _handle_tool_calls", "def _handle_final_result", "process_tool_calls"),
    ),
    (
        "pydantic_ai_slim/pydantic_ai/_output.py",
        ("class OutputSchema", "class OutputToolset", "process_tool_call", "OutputToolset.for_run_step"),
    ),
    (
        "pydantic_ai_slim/pydantic_ai/output.py",
        ("class ToolOutput", "OutputContext", "OutputSpec"),
    ),
    (
        "pydantic_ai_slim/pydantic_ai/result.py",
        ("class FinalResult", "EndRun"),
    ),
    ("tests/test_agent.py", ("test_early_strategy", "test_graceful_strategy", "test_exhaustive_strategy")),
    ("tests/test_agent_output_schemas.py", ("output", "schema")),
    ("docs/agent.md", ("end_strategy", "output_type")),
)

PYDANTIC_REVIEW_TASK = RealTask(
    slug=PYDANTIC_REVIEW_SLUG,
    repository=PYDANTIC_REVIEW_REPOSITORY,
    issue=PYDANTIC_REVIEW_ISSUE,
    title=PYDANTIC_REVIEW_TITLE,
    target_directory="pydantic-ai",
    statement=PYDANTIC_REVIEW_STATEMENT,
    test_command=PYDANTIC_REVIEW_TEST_COMMAND,
    evidence_files=PYDANTIC_REVIEW_EVIDENCE_FILES,
    acceptance_code="",
    required_surfaces=(
        (
            "review_strategy_surface",
            r"end_strategy.{0,100}review|review.{0,100}end_strategy",
        ),
        ("patch_surface", r"patch_result|json.?patch|JsonPatch"),
        ("confirmation_surface", r"confirm_result|confirmation"),
    ),
)


PYDANTIC_GRAPH_7785_ACCEPTANCE = r'''from __future__ import annotations

import asyncio
import json

from pydantic_graph import GraphBuilder, StepContext, reduce_list_append
from pydantic_graph.id_types import ForkID, JoinID


async def run_repro() -> list[object]:
    """Reproduce issue #7785 without timing-dependent sleeps."""
    fan_started = asyncio.Event()
    graph = GraphBuilder(name="issue_7785", input_type=str, output_type=list)

    @graph.step
    async def root(ctx: StepContext[None, None, str]) -> str:
        return ctx.inputs

    @graph.step
    async def fan_prepare(ctx: StepContext[None, None, object]) -> list[int]:
        fan_started.set()
        return [1, 2, 3]

    @graph.step
    async def fan_unit(ctx: StepContext[None, None, int]) -> int:
        return ctx.inputs * 10

    fan_join = graph.join(reduce_list_append, initial_factory=list, node_id="fan_join")

    @graph.step
    async def fan_result(ctx: StepContext[None, None, list]) -> list[int]:
        return sorted(ctx.inputs)

    @graph.step
    async def plain_producer(ctx: StepContext[None, None, object]) -> str:
        await fan_started.wait()
        return "plain"

    merge = graph.join(reduce_list_append, initial_factory=list, node_id="merge")

    @graph.step
    async def downstream(ctx: StepContext[None, None, list]) -> list[object]:
        return ctx.inputs

    graph.add_edge(graph.start_node, root)
    graph.add_edge(root, fan_prepare)
    graph.add_edge(root, plain_producer)
    graph.add_mapping_edge(
        fan_prepare,
        fan_unit,
        fork_id=ForkID("fan_fork"),
        downstream_join_id=JoinID("fan_join"),
    )
    graph.add_edge(fan_unit, fan_join)
    graph.add_edge(fan_join, fan_result)
    graph.add_edge(fan_result, merge)
    graph.add_edge(plain_producer, merge)
    graph.add_edge(merge, downstream)
    graph.add_edge(downstream, graph.end_node)
    return await graph.build().run(inputs="go")


def validate(result: list[object]) -> None:
    # `merge` uses reduce_list_append, so the fan branch contributes its
    # reduced list as one item alongside the plain producer's string.
    assert len(result) == 2, result
    assert result.count("plain") == 1, result
    assert any(
        isinstance(value, list) and sorted(value) == [10, 20, 30]
        for value in result
    ), result


async def main() -> dict[str, object]:
    # Repeat the deterministic graph to catch fixes that only work for one
    # scheduling order while keeping the oracle independent of timing.
    results = []
    for _ in range(3):
        result = await run_repro()
        validate(result)
        results.append(result)
    return {"accepted": True, "runs": results, "expected": ["plain", [10, 20, 30]]}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main())))
'''


PYDANTIC_GRAPH_7785_STATEMENT = """# Real GitHub task

- Repository: https://github.com/pydantic/pydantic-ai.git
- Package: `pydantic-graph`
- Issue: https://github.com/pydantic/pydantic-ai/issues/7785
- Title: `join()` with a fanned producer silently drops that branch's contribution

## Problem

`pydantic-graph` can silently lose a completed fan-out branch when a downstream
`join()` combines that branch with an ordinary producer.  The failure is
deterministic and comes from the no-active-task reducer-finalization path: an
intermediate join can be finalized and dispatch its downstream task, while a
second join is finalized in the same pass before that newly dispatched task has
delivered its contribution.

The public behavior must be correct for the graph shape in the issue: the final
join must see both producers, including the reduced result of the mapped branch.
Because the final join uses `reduce_list_append`, that reduced list is one item
alongside the `"plain"` item: the result contains `"plain"` and `[10, 20, 30]`.

## Required behavior

Implement a focused fix in the graph execution/building code.  The exact
algorithm is yours, but it must preserve the existing reducer and fork
semantics rather than adding a timing delay or a special case for the issue's
node names.

Add a deterministic regression test using the public `GraphBuilder` API.  It
must cover a mapped/fanned producer whose result passes through an intermediate
join before converging with an ordinary producer at a second join.  The final
result must contain `"plain"`, `10`, `20`, and `30` (order may be scheduler
dependent).  Keep the existing graph tests green.

## Acceptance contract

- The issue reproduction passes repeatedly without sleeps or timing heuristics.
- The fanned branch contributes its reduced `[10, 20, 30]` value to the downstream join.
- Existing map, broadcast, reducer, and nested-join behavior remains green.
- A focused regression test is added under `tests/graph/`.
- The diff is limited to the smallest relevant implementation/test surface;
  do not change dependencies, generated files, or unrelated packages.

## Suggested workflow

1. Read the repository and package instructions plus the existing broadcast/map
   tests.
2. Trace `active_reducers`, `_get_completed_fork_runs`, and the fallback path
   used when there are no active tasks.
3. Reproduce the issue before editing.
4. Make the smallest general fix, add the regression, and run the targeted
   graph-builder suite.

Do not commit or push. Work only in the provided detached worktree.
"""


PYDANTIC_GRAPH_7785 = RealTask(
    slug="pydantic-ai-7785-fanned-join",
    repository="https://github.com/pydantic/pydantic-ai.git",
    issue="https://github.com/pydantic/pydantic-ai/issues/7785",
    title="`join()` with a fanned producer silently drops that branch's contribution",
    target_directory="pydantic-ai-7785",
    statement=PYDANTIC_GRAPH_7785_STATEMENT,
    test_command=(
        "uv",
        "run",
        "--frozen",
        "pytest",
        "tests/graph/builder/test_broadcast_and_spread.py",
        "-q",
        "--disable-warnings",
        "--maxfail=5",
    ),
    evidence_files=(
        ("AGENTS.md", ("Gathering context on the task", "Development workflow", "When to verify")),
        ("tests/AGENTS.md", ("Testing philosophy", "Test File Structure", "Key Fixtures")),
        (
            "pydantic_graph/pydantic_graph/graph_builder.py",
            (
                "class _GraphIterator",
                "async def iter_graph",
                "active_reducers",
                "_get_completed_fork_runs",
                "_is_fork_run_completed",
                "_compute_intermediate_join_nodes",
            ),
        ),
        (
            "pydantic_graph/pydantic_graph/join.py",
            ("class JoinState", "class Join", "reduce_list_append"),
        ),
        (
            "pydantic_graph/pydantic_graph/parent_forks.py",
            ("intermediate_nodes", "class ParentFork"),
        ),
        (
            "tests/graph/builder/test_broadcast_and_spread.py",
            ("downstream_join_id", "test_parallel_maps_with_downstream_join_id", "nested"),
        ),
        ("tests/graph/builder/test_graph_execution.py", ("GraphBuilder", "graph.run")),
    ),
    acceptance_code=PYDANTIC_GRAPH_7785_ACCEPTANCE,
    required_surfaces=(
        ("graph_execution_surface", r"active_reducers|intermediate_join_nodes|_get_completed_fork_runs"),
        ("fork_join_surface", r"add_mapping_edge|downstream_join|reduce_list_append|join"),
    ),
)


PYTEST_14635_ACCEPTANCE = r'''from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = (Path.cwd() / "src").resolve()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture_project(root: Path) -> tuple[Path, Path, Path]:
    tests = root / "tests"
    components = tests / "components"
    water_heater = components / "water_heater"
    tts = components / "tts"
    for directory in (tests, components, water_heater, tts):
        directory.mkdir(parents=True, exist_ok=True)
        _write(directory / "__init__.py", "")

    _write(tests / "conftest.py", "import pytest\n")
    _write(
        components / "conftest.py",
        """\
import pytest

@pytest.fixture
def cache_dir_side_effect():
    return None

@pytest.fixture
def mock_init_cache_dir(cache_dir_side_effect):
    return cache_dir_side_effect

@pytest.fixture
def mock_cache_dir(mock_init_cache_dir):
    return mock_init_cache_dir
""",
    )
    _write(
        water_heater / "test_water_heater.py",
        "def test_water_heater():\n    pass\n",
    )
    _write(
        tts / "conftest.py",
        """\
import pytest

@pytest.fixture(autouse=True)
def mock_cache_dir(mock_cache_dir):
    return mock_cache_dir
""",
    )
    _write(
        tts / "test_init.py",
        """\
import pytest

@pytest.mark.parametrize("cache_dir_side_effect", ["error_value"])
def test_setup_no_access(mock_init_cache_dir):
    assert mock_init_cache_dir == "error_value"
""",
    )
    config_test = tests / "test_config_entries.py"
    _write(config_test, "def test_config():\n    pass\n")
    return water_heater, config_test, tts / "test_init.py"


def _collect(root: Path, paths: tuple[Path, ...]) -> dict[str, object]:
    bootstrap_dir = root / "__astra_bootstrap"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    _write(
        bootstrap_dir / "sitecustomize.py",
        """\
import sys
import types

version_module = types.ModuleType("_pytest._version")
version_module.version = "9.1.0.dev0"
version_module.version_tuple = (9, 1, 0, "dev0")
sys.modules["_pytest._version"] = version_module
import _pytest

_pytest._version = version_module
""",
    )
    environment = os.environ.copy()
    old_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(bootstrap_dir), str(SOURCE_ROOT), old_pythonpath) if value
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *(str(path) for path in paths)],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "fixture collection failed:\n"
            + completed.stdout[-4000:]
            + completed.stderr[-4000:]
        )
    if "test_setup_no_access" not in completed.stdout:
        raise AssertionError(f"target test was not collected:\n{completed.stdout[-4000:]}")
    return {
        "returncode": completed.returncode,
        "collected_target": "test_setup_no_access" in completed.stdout,
        "stdout_tail": completed.stdout[-1000:],
    }


def main() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="pytest-14635-oracle-") as temporary:
        root = Path(temporary)
        water_heater, config_test, target_test = _fixture_project(root)
        # The first order is the reported failure trigger. The second order
        # guards against a fix that only special-cases one collection order.
        orders = (
            (water_heater, config_test, target_test),
            (target_test, water_heater, config_test),
            (config_test, water_heater, target_test),
        )
        runs = [_collect(root, order) for order in orders]
    return {"accepted": True, "runs": runs}


if __name__ == "__main__":
    print(json.dumps(main()))
'''


PYTEST_14635_STATEMENT = """# Real GitHub task

- Repository: https://github.com/pytest-dev/pytest.git
- Issue: https://github.com/pytest-dev/pytest/issues/14635
- Related fix: https://github.com/pytest-dev/pytest/pull/14645
- Title: Fixture closure changes when common parent directories are collected repeatedly

## Problem

Pytest 9.1.x can lose a transitive parametrized fixture from a test's fixture
closure when multiple test paths with shared parent directories are collected
in one invocation. The same target test can collect successfully in isolation
or when the paths are given in another order, but fail with `function uses no
argument ...` after an unrelated directory was collected first.

The regression comes from re-collection creating fresh `Directory` nodes while
fixture registration and closure state are keyed by node identity. The fix
must preserve the identity of already-collected directory children without
hardcoding Home Assistant or this reproduction's paths.

## Required behavior

1. Make the collection/fixture behavior independent of the order in which
   unrelated paths sharing a parent are supplied.
2. Preserve normal collection, duplicate-path handling, and third-party
   directory collector behavior.
3. Add a deterministic regression test under `testing/` that exercises a
   transitive parametrized fixture and repeated collection of common parents.
4. Keep the implementation focused; do not change dependencies or generated
   files.

## Acceptance contract

- The independent oracle repeats the official fixture topology in three path
  orders and collects the parametrized target every time.
- The targeted pytest collector tests pass.
- The diff contains both a collector implementation change and a regression
  test; production-only patches are incomplete.
- The solution must be general rather than a special case for the fixture or
  directory names in the oracle.

## Suggested workflow

1. Read `src/_pytest/main.py`, the node/fixture collection code, and the
   existing `testing/test_conftest.py` tests.
2. Reproduce the order-dependent collection failure before editing.
3. Trace how `_collection_cache`, `Directory` nodes, and fixture registration
   interact during re-collection.
4. Implement the smallest identity-preserving fix and add the regression.
5. Run the targeted collector tests and the issue oracle.

Do not commit or push. Work only in the provided detached worktree.
"""


PYTEST_14635_VERIFICATION_PREFIX = (
    "uv",
    "run",
    "--no-project",
    "--with",
    "pluggy>=1.5,<2",
    "--with",
    "packaging>=22",
    "--with",
    "pygments>=2.7.2",
    "--with",
    "iniconfig>=1.0.1",
    "--with",
    "colorama>=0.4",
)


# Keep the command itself one line so every worker serializes the exact same
# allowlisted string. The temporary sitecustomize module uses chr(10) instead
# of embedded newline escapes, which avoids JSON/protocol unescaping changes.
PYTEST_14635_TEST_CODE = (
    "import os,sys,tempfile,pathlib;"
    "b=pathlib.Path(tempfile.mkdtemp(prefix='pytest-benchmark-bootstrap-'));"
    "pathlib.Path(b,'sitecustomize.py').write_text("
    "\"import sys,types\"+chr(10)+"
    "\"m=types.ModuleType('_pytest._version')\"+chr(10)+"
    "\"m.version='9.1.0.dev0'\"+chr(10)+"
    "\"m.version_tuple=(9,1,0,'dev0')\"+chr(10)+"
    "\"sys.modules['_pytest._version']=m\"+chr(10)+"
    "\"import _pytest\"+chr(10)+"
    "\"_pytest._version=m\"+chr(10),encoding='utf-8');"
    "s=os.path.abspath('src');o=os.environ.get('PYTHONPATH');"
    "os.environ['PYTHONPATH']=os.pathsep.join([str(b),s]+([o] if o else []));"
    "sys.path[:0]=[str(b),s];import sitecustomize,pytest;"
    "raise SystemExit(pytest.main(['testing/test_conftest.py','-q','--disable-warnings','--maxfail=5','-k',"
    "'test_conftest_fixture_from_ancestor_above_rootdir or fixture_closure_order_independence_with_parametrize']))"
)


PYTEST_14635 = RealTask(
    slug="pytest-14635-fixture-closure",
    repository="https://github.com/pytest-dev/pytest.git",
    issue="https://github.com/pytest-dev/pytest/issues/14635",
    title="Fixture closure changes when common parent directories are collected repeatedly",
    target_directory="pytest-14635-fixture-closure",
    statement=PYTEST_14635_STATEMENT,
    test_command=PYTEST_14635_VERIFICATION_PREFIX + (
        "python",
        "-c",
        PYTEST_14635_TEST_CODE,
    ),
    evidence_files=(
        ("src/_pytest/main.py", ("_collection_cache", "_collect_one_node", "handle_dupes", "collect_one_node")),
        ("src/_pytest/nodes.py", ("class Directory", "class Node")),
        ("src/_pytest/fixtures.py", ("getfixtureinfo", "getfixtureclosure", "FixtureManager")),
        ("testing/test_conftest.py", ("test_uses_ancestor", "Pytester", "fixture")),
        ("testing/test_collect.py", ("Directory", "collect")),
    ),
    acceptance_code=PYTEST_14635_ACCEPTANCE,
    required_surfaces=(
        ("collection_identity_surface", r"_collection_cache|Directory|handle_dupes"),
        ("fixture_regression_surface", r"14635|fixture_closure|parametr"),
    ),
    verification_prefix=PYTEST_14635_VERIFICATION_PREFIX,
    # Lattice executes allowlisted argv directly rather than through a shell;
    # keep its in-transaction check free of a multi-token Python -c payload.
    lattice_verification_command=(
        "uv run --no-project --with-editable . pytest testing/test_conftest.py -q "
        "--disable-warnings --maxfail=5"
    ),
    astra_context_budget_tokens=36_000,
    astra_max_page_faults=6,
    astra_max_turns=10,
)


def available_tasks() -> dict[str, RealTask]:
    """Return task definitions that are safe to use from the benchmark CLI."""
    return {
        PYDANTIC_REVIEW_TASK.slug: PYDANTIC_REVIEW_TASK,
        PYDANTIC_GRAPH_7785.slug: PYDANTIC_GRAPH_7785,
        PYTEST_14635.slug: PYTEST_14635,
    }


def get_real_task(slug: str = PYDANTIC_REVIEW_SLUG) -> RealTask:
    """Resolve an allowlisted benchmark task without accepting paths or code."""

    task = available_tasks().get(slug)
    if task is None:
        available = ", ".join(sorted(available_tasks()))
        raise ValueError(f"unknown real-task benchmark {slug!r}; choose one of: {available}")
    return task
