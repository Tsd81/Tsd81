"""CrewAI hierarchical orchestrator.

When ANTHROPIC_API_KEY is set (and crewai is importable), a task runs as a real
CrewAI hierarchical crew: a manager agent (the core) delegates to the role
agents, which use MCP-style connector tools. Events are bridged from the crew
(running in a worker thread) back onto the asyncio loop so the graph animates.

When no key is present — or if a crew errors — it delegates to the custom
`Orchestrator` (deterministic offline mock, precise event emission). Same
interface, same event contract, same graph.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List

from .broadcaster import Broadcaster
from .connectors import get_connectors
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
from .llm import get_provider
from .nodes import load_nodes_config
from .orchestrator import Orchestrator
from .tasks import TaskRecord, store


def crewai_available() -> bool:
    try:
        import crewai  # noqa: F401
        return True
    except Exception:
        return False


def _model_string() -> str:
    model = os.getenv("MODEL", "claude-sonnet-4-5").strip()
    return model if "/" in model else f"anthropic/{model}"


class CrewOrchestrator:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self.b = broadcaster
        self.fallback = Orchestrator(broadcaster)  # custom/offline path + safety net
        self.provider = get_provider()
        cfg = load_nodes_config()
        self.core_id = cfg["core"]["id"]
        self.roles = {n["id"]: n for n in cfg["nodes"] if n.get("type") == "agent"}
        self.label_to_id = {n["label"]: n["id"] for n in cfg["nodes"]}
        self.connectors = get_connectors()
        self.agent_tools: Dict[str, List[str]] = {}
        for n in cfg["nodes"]:
            if n.get("type") == "tool":
                for a in n.get("connects", []):
                    self.agent_tools.setdefault(a, []).append(n["id"])
        self._running = False

    @property
    def busy(self) -> bool:
        return self._running or self.fallback.busy

    @property
    def engine(self) -> str:
        return "crewai" if (self.provider.is_real and crewai_available()) else "custom-mock"

    async def run_task(self, text: str) -> dict:
        # No real key or crewai missing → precise offline path.
        if not self.provider.is_real or not crewai_available():
            return await self.fallback.run_task(text)

        if self._running:
            raise RuntimeError("orchestrator busy")
        self._running = True
        rec = store.new_task(title=text.strip()[:80] or "Untitled task")
        loop = asyncio.get_running_loop()
        try:
            await self.b.broadcast(CoreStateEvent(state="orchestrating"))
            await self.b.broadcast(TaskCreated(id=rec.id, title=rec.title, assignee=self.core_id))
            await self.b.broadcast(TaskUpdate(id=rec.id, state="running"))
            await self.b.broadcast(LogEvent(level="info", msg="Running CrewAI hierarchical crew"))

            answer = await asyncio.to_thread(self._kickoff_blocking, text, rec, loop)
            rec.output = answer
            rec.state = "done"
            await self.b.broadcast(TaskUpdate(id=rec.id, state="done", output=answer))
            await self.b.broadcast(LogEvent(level="info", msg=f"Task {rec.id} complete (crewai)"))
            return store.detail(rec.id)  # type: ignore[return-value]
        except Exception as exc:
            # Safety net: never leave the operator without a result.
            await self.b.broadcast(LogEvent(level="warn", msg=f"Crew failed ({exc}); using fallback"))
            self._running = False
            return await self.fallback.run_task(text)
        finally:
            await self.b.broadcast(CoreStateEvent(state="standby"))
            store.save()
            self._running = False

    # ── event bridge (called from the worker thread) ──
    def _emit(self, loop: asyncio.AbstractEventLoop, event: Any) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self.b.broadcast(event), loop)
        except Exception:
            pass

    def _make_tool(self, loop, rec: TaskRecord, agent_role: str, tool_node: str, action: str):
        from crewai.tools import tool as crew_tool

        connector = self.connectors[tool_node]
        core_id = self.core_id

        @crew_tool(f"{tool_node}_{action}")
        def _run(query: str = "") -> str:
            """Call the connected data/tool service and return JSON results."""
            self._emit(loop, EdgeActive(**{"from": agent_role}, to=tool_node, on=True))
            self._emit(loop, ToolCall(node=tool_node, action=action,
                                      summary=f"{agent_role} → {tool_node}.{action}"))
            try:
                fut = asyncio.run_coroutine_threadsafe(connector.call(action, query=query), loop)
                res = fut.result(timeout=10)
                ok = True
            except Exception as exc:
                res, ok = {"error": str(exc)}, False
            rec.agent(agent_role).tools.append(
                {"ts": _now(), "node": tool_node, "action": action, "ok": ok,
                 "summary": f"{tool_node}.{action}"})
            self._emit(loop, ToolResult(node=tool_node, action=action, ok=ok,
                                        summary=f"{tool_node}.{action}"))
            self._emit(loop, EdgeActive(**{"from": agent_role}, to=tool_node, on=False))
            return json.dumps(res)

        return _run

    def _agent_step_cb(self, loop, rec: TaskRecord, role_id: str):
        core_id = self.core_id
        seen = {"started": False}

        def cb(_step: Any) -> None:
            if not seen["started"]:
                seen["started"] = True
                self._emit(loop, EdgeActive(**{"from": core_id}, to=role_id, on=True))
                self._emit(loop, AgentStatus(node=role_id, state="working"))
                rec.agent(role_id).state = "working"
            rec.agent(role_id).log("crew step")

        return cb

    def _build_agents(self, loop, rec: TaskRecord):
        from crewai import LLM, Agent

        llm = LLM(model=_model_string())
        _ACTION = {"email": "search", "calendar": "list_events", "drive": "search", "memory": "recall"}
        agents = []
        for rid, rdef in self.roles.items():
            tools = [self._make_tool(loop, rec, rid, tnode, _ACTION.get(tnode, "call"))
                     for tnode in self.agent_tools.get(rid, []) if tnode in self.connectors]
            agents.append(Agent(
                role=rdef["label"],
                goal=rdef.get("role", f"Act as the {rdef['label']} specialist."),
                backstory=f"You are the {rdef['label']} agent on a personal AI team.",
                llm=llm,
                tools=tools,
                allow_delegation=False,
                verbose=False,
                step_callback=self._agent_step_cb(loop, rec, rid),
            ))
        return agents, llm

    def _kickoff_blocking(self, text: str, rec: TaskRecord, loop) -> str:
        from crewai import Crew, Process, Task

        agents, llm = self._build_agents(loop, rec)
        task = Task(
            description=text,
            expected_output="A clear, concise, actionable answer for the user.",
        )
        crew = Crew(
            agents=agents,
            tasks=[task],
            process=Process.hierarchical,
            manager_llm=llm,
            verbose=False,
        )
        result = crew.kickoff()
        return str(getattr(result, "raw", result))


def _now() -> int:
    from .events import now_ms
    return now_ms()
