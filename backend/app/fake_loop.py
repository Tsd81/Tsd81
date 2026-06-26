"""Phase 0 fake event generator.

Emits realistic lifecycle events on a loop so the dashboard can be proven
to be driven by the live socket (not a hardcoded client-side animation).

This whole module is replaced by the real CrewAI orchestrator in Phase 2.
"""
from __future__ import annotations

import asyncio
import random

from .broadcaster import broadcaster
from .events import (
    AgentStatus,
    CoreStateEvent,
    EdgeActive,
    LogEvent,
    TaskCreated,
    TaskUpdate,
    ToolCall,
    ToolResult,
)
from .nodes import agent_ids, load_nodes_config, tool_ids

_TASK_TITLES = [
    "Draft Q3 outreach plan",
    "Summarize competitor research",
    "Reconcile last month's invoices",
    "Prepare board update deck",
    "Triage inbound support tickets",
    "Plan product launch timeline",
]
_TOOL_ACTIONS = {
    "email": ["search", "send", "list_threads"],
    "calendar": ["list_events", "create_event", "find_slot"],
    "drive": ["search", "read_file", "list"],
    "memory": ["recall", "store"],
}


def _tools_for_agent(agent_id: str) -> list[str]:
    cfg = load_nodes_config()
    return [n["id"] for n in cfg["nodes"]
            if n.get("type") == "tool" and agent_id in n.get("connects", [])]


async def _run_one_task(seq: int) -> None:
    agents = agent_ids()
    assignees = random.sample(agents, k=random.randint(1, 3))
    task_id = f"t{seq}"
    title = random.choice(_TASK_TITLES)

    await broadcaster.broadcast(CoreStateEvent(state="orchestrating"))
    await broadcaster.broadcast(TaskCreated(id=task_id, title=title, assignee=assignees[0]))
    await broadcaster.broadcast(LogEvent(level="info", msg=f"Orchestrating: {title}"))
    await broadcaster.broadcast(TaskUpdate(id=task_id, state="running"))

    async def work(agent: str) -> None:
        await broadcaster.broadcast(EdgeActive(**{"from": "core"}, to=agent, on=True))
        await broadcaster.broadcast(AgentStatus(node=agent, state="thinking"))
        await asyncio.sleep(random.uniform(0.4, 1.2))
        await broadcaster.broadcast(AgentStatus(node=agent, state="working"))

        for tool in _tools_for_agent(agent):
            if random.random() < 0.6:
                action = random.choice(_TOOL_ACTIONS.get(tool, ["call"]))
                await broadcaster.broadcast(EdgeActive(**{"from": agent}, to=tool, on=True))
                await broadcaster.broadcast(ToolCall(node=tool, action=action,
                                                     summary=f"{agent} → {tool}.{action}"))
                await asyncio.sleep(random.uniform(0.3, 0.8))
                await broadcaster.broadcast(ToolResult(node=tool, action=action, ok=True,
                                                       summary="ok (mock data)"))
                await broadcaster.broadcast(EdgeActive(**{"from": agent}, to=tool, on=False))

        await asyncio.sleep(random.uniform(0.5, 1.5))
        await broadcaster.broadcast(AgentStatus(node=agent, state="done"))
        await broadcaster.broadcast(EdgeActive(**{"from": "core"}, to=agent, on=False))
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await broadcaster.broadcast(AgentStatus(node=agent, state="idle"))

    await asyncio.gather(*(work(a) for a in assignees))

    await broadcaster.broadcast(TaskUpdate(id=task_id, state="done",
                                           output="(mock) completed"))
    await broadcaster.broadcast(LogEvent(level="info", msg=f"Done: {title}"))
    await broadcaster.broadcast(CoreStateEvent(state="standby"))


async def fake_event_loop() -> None:
    """Background task: continuously runs fake tasks with idle gaps."""
    seq = 1
    # Occasionally tickle a random tool even between tasks, for liveliness.
    while True:
        try:
            await _run_one_task(seq)
            seq += 1
            await asyncio.sleep(random.uniform(1.5, 3.5))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never let the loop die silently
            await broadcaster.broadcast(LogEvent(level="error", msg=f"fake loop: {exc}"))
            await asyncio.sleep(2.0)
