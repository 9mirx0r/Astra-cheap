#!/usr/bin/env python3
"""Stable data contracts shared by the Astra-Ultra runtime.

The original project exposed independent CLI utilities.  These small value
objects provide one explicit seam between deterministic context preparation,
workers, patch application, and benchmark telemetry without forcing the
utilities themselves to know about one another.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _tuple_strings(values: Iterable[str] | None) -> Tuple[str, ...]:
    if values is None:
        return ()
    result = tuple(str(value) for value in values if str(value).strip())
    return result


@dataclass(frozen=True)
class TaskSpec:
    """A bounded, reproducible unit of work for an Astra runtime run."""

    task_id: str
    objective: str
    root: Path
    test_command: Tuple[str, ...] = ()
    acceptance_command: Tuple[str, ...] = ()
    allowed_paths: Tuple[str, ...] = ()
    focus_paths: Tuple[str, ...] = ()
    focus_terms: Tuple[str, ...] = ()
    context_budget_tokens: int = 4096
    page_budget_tokens: int = 1200
    max_page_faults: int = 4
    max_turns: int = 4
    max_recoveries: int = 2
    verification_timeout_seconds: int = 900

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.objective.strip():
            raise ValueError("objective must not be empty")
        object.__setattr__(self, "root", Path(self.root).resolve())
        for name in (
            "context_budget_tokens",
            "page_budget_tokens",
            "max_page_faults",
            "max_turns",
            "max_recoveries",
            "verification_timeout_seconds",
        ):
            value = getattr(self, name)
            if name in {"context_budget_tokens", "page_budget_tokens", "max_turns", "verification_timeout_seconds"}:
                _positive_int(value, name)
            else:
                _non_negative_int(value, name)
        if self.page_budget_tokens > self.context_budget_tokens:
            raise ValueError("page_budget_tokens cannot exceed context_budget_tokens")
        for name in ("test_command", "acceptance_command", "allowed_paths", "focus_paths", "focus_terms"):
            object.__setattr__(self, name, _tuple_strings(getattr(self, name)))
        if self.test_command and not self.test_command[0].strip():
            raise ValueError("test_command cannot start with an empty executable")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], root: Path | None = None) -> "TaskSpec":
        """Build a task from JSON/YAML-like data used by benchmark manifests."""
        values = dict(data)
        if root is not None:
            values["root"] = root
        if "root" not in values:
            raise ValueError("task spec requires root")
        return cls(
            task_id=str(values.get("task_id", values.get("id", "task"))),
            objective=str(values.get("objective", values.get("description", ""))),
            root=Path(values["root"]),
            test_command=tuple(values.get("test_command", ())),
            acceptance_command=tuple(values.get("acceptance_command", ())),
            allowed_paths=tuple(values.get("allowed_paths", ())),
            focus_paths=tuple(values.get("focus_paths", ())),
            focus_terms=tuple(values.get("focus_terms", ())),
            context_budget_tokens=int(values.get("context_budget_tokens", 4096)),
            page_budget_tokens=int(values.get("page_budget_tokens", 1200)),
            max_page_faults=int(values.get("max_page_faults", 4)),
            max_turns=int(values.get("max_turns", 4)),
            max_recoveries=int(values.get("max_recoveries", 2)),
            verification_timeout_seconds=int(values.get("verification_timeout_seconds", 900)),
        )

    def to_dict(self) -> Dict[str, Any]:
        values = asdict(self)
        values["root"] = str(self.root)
        return values


@dataclass(frozen=True)
class ContextPage:
    """An immutable, source-hashed slice that can be handed to a worker."""

    page_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    sha256: str
    reason: str
    estimated_tokens: int
    authority: str = "untrusted_source_data"

    def __post_init__(self) -> None:
        if not self.page_id or not self.path:
            raise ValueError("context pages require page_id and path")
        if self.start_line <= 0 or self.end_line < self.start_line:
            raise ValueError("context page line range is invalid")
        if self.estimated_tokens < 0:
            raise ValueError("context page token estimate cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextRequest:
    """A bounded request for additional context after an initial page miss."""

    paths: Tuple[str, ...] = ()
    terms: Tuple[str, ...] = ()
    max_lines: int = 50
    reason: str = "worker requested more evidence"

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", _tuple_strings(self.paths))
        object.__setattr__(self, "terms", _tuple_strings(self.terms))
        _positive_int(self.max_lines, "max_lines")
        if self.max_lines > 200:
            raise ValueError("max_lines cannot exceed 200")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ContextRequest":
        paths = data.get("paths", data.get("files", ()))
        terms = data.get("terms", data.get("focus_terms", ()))
        if isinstance(paths, str):
            paths = (paths,)
        if isinstance(terms, str):
            terms = (terms,)
        return cls(
            paths=tuple(paths or ()),
            terms=tuple(terms or ()),
            max_lines=int(data.get("max_lines", 50)),
            reason=str(data.get("reason", "worker requested more evidence")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkerResponse:
    """Normalized worker output; no provider-specific shape leaks downstream."""

    kind: str
    patch: str = ""
    context_request: Optional[ContextRequest] = None
    message: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {"patch", "context_request", "final", "error"}:
            raise ValueError(f"unsupported worker response kind: {self.kind}")
        if self.kind == "patch" and not self.patch.strip():
            raise ValueError("patch worker responses require non-empty patch text")
        if self.kind == "context_request" and self.context_request is None:
            raise ValueError("context_request responses require a request")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkerResponse":
        kind = str(data.get("kind", data.get("type", "final"))).lower()
        if kind in {"context", "context_fault", "request_context"}:
            kind = "context_request"
        if kind in {"complete", "done", "answer"}:
            kind = "final"
        request_data = data.get("context_request", data.get("request"))
        request = None
        if kind == "context_request":
            request = ContextRequest.from_mapping(request_data or data)
        usage = data.get("usage", {})
        normalized_usage = {
            str(key): int(value)
            for key, value in usage.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        }
        patch = str(data.get("patch", data.get("diff", "")))
        return cls(
            kind=kind,
            patch=patch,
            context_request=request,
            message=str(data.get("message", data.get("answer", ""))),
            usage=normalized_usage,
            raw=dict(data),
        )


@dataclass
class Telemetry:
    """Run-level measurements with explicit unknowns instead of fake zeroes."""

    started_at: float
    finished_at: Optional[float] = None
    turns: int = 0
    page_faults: int = 0
    recovery_attempts: int = 0
    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_output_tokens: Optional[int] = None
    tool_call_count: Optional[int] = None
    stages_ms: Dict[str, float] = field(default_factory=dict)
    events: list[Dict[str, Any]] = field(default_factory=list)

    def record_usage(self, usage: Mapping[str, int]) -> None:
        aliases = {
            "input_tokens": "input_tokens",
            "prompt_tokens": "input_tokens",
            "cached_input_tokens": "cached_input_tokens",
            "cached_tokens": "cached_input_tokens",
            "output_tokens": "output_tokens",
            "completion_tokens": "output_tokens",
            "reasoning_output_tokens": "reasoning_output_tokens",
            "reasoning_tokens": "reasoning_output_tokens",
            "tool_call_count": "tool_call_count",
        }
        for key, value in usage.items():
            target = aliases.get(key)
            if target is None:
                continue
            numeric = max(0, int(value))
            current = getattr(self, target)
            # Each WorkerResponse represents one provider turn.  Turn-level
            # usage must be added; taking a max would silently undercount
            # context faults and recovery turns.
            setattr(self, target, numeric if current is None else current + numeric)

    def add_event(self, event: str, **data: Any) -> None:
        self.events.append({"event": event, **data})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": (
                None if self.finished_at is None else round(self.finished_at - self.started_at, 4)
            ),
            "turns": self.turns,
            "page_faults": self.page_faults,
            "recovery_attempts": self.recovery_attempts,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "tool_call_count": self.tool_call_count,
            "stages_ms": dict(self.stages_ms),
            "events": list(self.events),
        }


@dataclass(frozen=True)
class RunResult:
    """Serializable result used by the CLI and benchmark harness."""

    task_id: str
    status: str
    accepted: bool
    state_history: Tuple[str, ...]
    message: str
    changed_paths: Tuple[str, ...] = ()
    telemetry: Mapping[str, Any] = field(default_factory=dict)
    verification: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "accepted": self.accepted,
            "state_history": list(self.state_history),
            "message": self.message,
            "changed_paths": list(self.changed_paths),
            "telemetry": dict(self.telemetry),
            "verification": dict(self.verification),
        }
