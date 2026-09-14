from dataclasses import dataclass
import json

from agentdist.structures.agent import (
    AgentTrajectory,
    AgentTrajectoryTool,
)

from synthesis import RawPr, SynthesizedTask


@dataclass
class ChainSegment:
    raw_pr: RawPr
    task: SynthesizedTask
    handoff: str | None
    trajectory: AgentTrajectory



def finished_cleanly(export_json: dict) -> bool:
    """True iff the last message of an `opencode export` is a clean assistant stop.
    """

    messages = export_json.get("messages", [])
    return (
        bool(messages)
        and messages[-1].get("info", {}).get("role") == "assistant"
        and messages[-1].get("info", {}).get("finish") == "stop"
    )


def _tool_result_text(tool: AgentTrajectoryTool) -> str:
    if tool.result is None:
        return ""
    if isinstance(tool.result, str):
        return tool.result
    return json.dumps(tool.result)


def combine_segments(segments: list[ChainSegment]) -> dict:
    """Flatten N per-PR trajectories into one [system?, user, *solver][...] conversation.

    Each segment's own leading "user" step (the raw combined prompt actually
    sent to opencode) is dropped and replaced with an explicit
    [system(handoff), user(bare task)] pair, mirroring how
    long_context_midtraining represents a turn for training even though the
    solver itself received one combined string.
    """

    conversation: list[dict] = []
    for segment in segments:
        conversation.append({"role": "user", "content": segment.task.instruction})
        steps = segment.trajectory.steps
        start = 0
        while start < len(steps) and steps[start].role == "user":
            start += 1
        for step in steps[start:]:
            entry: dict = {"role": step.role, "content": step.message or "","tool_calls":[]}
            if step.reasoning_content:
                entry["reasoning_content"] = step.reasoning_content
            results = []
            for tool in step.tool_call:
                name = tool.name
                arguments = tool.arguments or {}
                entry["tool_calls"].append({"name": name, "arguments": arguments})
                results.append({"role": "tool", "content": _tool_result_text(tool)})
            conversation.append(entry)
            conversation.extend(results)

    return {
        "repo_full_name": segments[0].raw_pr.repo_full_name if segments else None,
        "pr_numbers": [segment.raw_pr.pr_number for segment in segments],
        "conversation": conversation,
        "turns": [
            {
                "pr_number": segment.raw_pr.pr_number,
                "base_commit": segment.raw_pr.base_commit,
                "task_title": segment.task.title,
                "session_id": segment.trajectory.metadata.session_id,
                "full_metrics": segment.trajectory.full_metrics.model_dump(),
            }
            for segment in segments
        ],
    }
