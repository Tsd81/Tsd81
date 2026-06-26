"""Pydantic models for the WebSocket event contract.

Source of truth: ../contract/events.schema.json
Keep this file and frontend/lib/events.ts in sync with that schema.
"""
from __future__ import annotations

import time
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

AgentState = Literal["idle", "thinking", "working", "done", "error"]
CoreState = Literal["standby", "orchestrating"]
TaskState = Literal["running", "done", "failed"]
LogLevel = Literal["info", "warn", "error"]


def now_ms() -> int:
    """Epoch milliseconds (matches JS Date.now())."""
    return int(time.time() * 1000)


class _Event(BaseModel):
    ts: int = Field(default_factory=now_ms)


class AgentStatus(_Event):
    type: Literal["agent.status"] = "agent.status"
    node: str
    state: AgentState


class ToolCall(_Event):
    type: Literal["tool.call"] = "tool.call"
    node: str
    action: str
    summary: Optional[str] = None


class ToolResult(_Event):
    type: Literal["tool.result"] = "tool.result"
    node: str
    action: str
    ok: bool
    summary: Optional[str] = None


class EdgeActive(_Event):
    type: Literal["edge.active"] = "edge.active"
    # `from` is reserved in Python, expose via alias.
    from_: str = Field(alias="from")
    to: str
    on: bool

    model_config = {"populate_by_name": True}


class TaskCreated(_Event):
    type: Literal["task.created"] = "task.created"
    id: str
    title: str
    assignee: str


class TaskUpdate(_Event):
    type: Literal["task.update"] = "task.update"
    id: str
    state: TaskState
    output: Optional[str] = None


class CoreStateEvent(_Event):
    type: Literal["core.state"] = "core.state"
    state: CoreState


class LogEvent(_Event):
    type: Literal["log"] = "log"
    level: LogLevel
    msg: str
    node: Optional[str] = None


class Snapshot(_Event):
    type: Literal["snapshot"] = "snapshot"
    core: CoreState
    nodes: Dict[str, AgentState]
    edges: List[dict] = Field(default_factory=list)


Event = Union[
    AgentStatus,
    ToolCall,
    ToolResult,
    EdgeActive,
    TaskCreated,
    TaskUpdate,
    CoreStateEvent,
    LogEvent,
    Snapshot,
]
