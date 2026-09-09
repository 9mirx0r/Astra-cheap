"""Independent black-box acceptance harness generation for benchmark tasks."""

from __future__ import annotations

from pathlib import Path

from real_task_catalog import RealTask


def make_acceptance_harness(path: Path, task: RealTask | None = None) -> None:
    """Write acceptance tests outside every agent worktree."""

    if task is not None and task.acceptance_code:
        path.write_text(task.acceptance_code, encoding="utf-8")
        return
    code = r'''from __future__ import annotations

import json
import sys

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


class Output(BaseModel):
    value: str


def _tools(info: AgentInfo):
    """Return output and generated function tools without duplicate names."""
    tools = []
    seen = set()
    for tool in [*(info.output_tools or []), *(info.function_tools or [])]:
        if tool.name not in seen:
            tools.append(tool)
            seen.add(tool.name)
    return tools


def _find_patch(info: AgentInfo):
    return next((tool for tool in _tools(info) if "patch" in tool.name.lower()), None)


def _is_confirmation_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in {"final_result", "output", "result"}:
        return False
    return any(marker in lowered for marker in ("confirm", "finalize", "review"))


def _find_confirmation(info: AgentInfo):
    return next((tool for tool in _tools(info) if _is_confirmation_name(tool.name)), None)


def _patch_args(tool):
    schema = tool.parameters_json_schema
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    key = next((key for key in props if any(word in key.lower() for word in ("patch", "operation", "ops"))), None)
    operation = {"op": "replace", "path": "/value", "value": "patched"}
    if key is None:
        return {"patches": [operation]}
    value_schema = props[key] if isinstance(props[key], dict) else {}
    if value_schema.get("type") == "array":
        return {key: [operation]}
    return {key: operation}


def run(mode: str) -> dict[str, object]:
    state = {"turn": 0}

    def model(messages, info: AgentInfo):
        turn = state["turn"]
        state["turn"] += 1
        if turn == 0:
            return ModelResponse(parts=[ToolCallPart("final_result", {"value": "initial"})])
        confirm = _find_confirmation(info)
        patch = _find_patch(info)
        if mode == "confirm":
            if confirm is None:
                raise AssertionError("review mode did not expose a confirmation tool")
            return ModelResponse(parts=[ToolCallPart(confirm.name, {})])
        if turn == 1:
            if patch is None:
                raise AssertionError("review mode did not expose a JSON patch tool")
            return ModelResponse(parts=[ToolCallPart(patch.name, _patch_args(patch))])
        if confirm is None:
            raise AssertionError("review mode did not expose a confirmation tool after patch")
        return ModelResponse(parts=[ToolCallPart(confirm.name, {})])

    agent = Agent(FunctionModel(model), output_type=Output, end_strategy="review")
    result = agent.run_sync("Extract the value and let me review it.")
    messages = result.all_messages()
    returns = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
    names = [part.tool_name.lower() for part in returns]
    expected = "initial" if mode == "confirm" else "patched"
    if result.output.value != expected:
        raise AssertionError(f"expected output {expected!r}, got {result.output.value!r}")
    if not any(name == "final_result" for name in names):
        raise AssertionError(f"final_result was not returned to the model: {names!r}")
    if not any(_is_confirmation_name(name) for name in names):
        raise AssertionError(f"confirmation was not recorded: {names!r}")
    if mode == "patch" and not any("patch" in name for name in names):
        raise AssertionError(f"patch was not recorded: {names!r}")
    return {"mode": mode, "output": result.output.model_dump(), "tool_return_names": names, "turns": state["turn"]}


if __name__ == "__main__":
    results = [run("confirm"), run("patch")]
    print(json.dumps({"accepted": True, "cases": results}))
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
