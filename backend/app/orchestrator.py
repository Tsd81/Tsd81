"""Hierarchical orchestrator: manager (core) delegates to role agents.

Flow per /task:
  1. core → orchestrating
  2. plan(): manager decides which agents to delegate to (LLM routing when a
     real provider is present, deterministic keyword routing otherwise)
  3. fan out to 1–3 agents in parallel; each optionally calls its connected
     tools (MCP-style connectors) and memory, then produces output via the LLM
  4. manager synthesizes a final answer from the agents' outputs
  5. core → standby

Every step emits the real contract events (agent.status, edge.active,
tool.call/result, task.*), so the graph reflects the actual run. All agent
work is also recorded into the TaskStore for the side panels.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import List, Tuple

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
from .llm import LLMProvider, get_provider
from .nodes import load_nodes_config
from .tasks import TaskRecord, store

# Keyword → role routing for the deterministic (offline) planner.
_KEYWORDS = {
    "research": "researcher", "find": "researcher", "investigate": "researcher",
    "learn": "researcher", "compare": "researcher", "analy": "analytics",
    "metric": "analytics", "report": "analytics", "data": "analytics",
    "plan": "strategist", "strategy": "strategist", "prioriti": "strategist",
    "sell": "sales", "deal": "sales", "pipeline": "sales", "outreach": "sales",
    "code": "developer", "bug": "developer", "implement": "developer",
    "architect": "engineering", "infra": "engineering", "system": "engineering",
    "design": "design", "brand": "design", "ux": "design", "ui": "design",
    "write": "editor", "edit": "editor", "draft": "editor", "proofread": "editor",
    "budget": "finance", "cost": "finance", "invoice": "finance", "financ": "finance",
    "schedule": "ops", "logistic": "ops", "coordinate": "chief_of_staff",
    "follow": "chief_of_staff", "email": "chief_of_staff", "meeting": "chief_of_staff",
    "social": "social", "post": "social", "content": "social",
    "contact": "crm", "customer": "crm", "relationship": "crm",
}


class Orchestrator:
    def __init__(self, broadcaster: Broadcaster, provider: LLMProvider | None = None) -> None:
        self.b = broadcaster
        self.provider = provider or get_provider()
        cfg = load_nodes_config()
        self.core_id = cfg["core"]["id"]
        self.roles = {n["id"]: n for n in cfg["nodes"] if n.get("type") == "agent"}
        self.connectors = get_connectors()
        # Invert the tool nodes' `connects` into agent_id -> [tool ids], since
        # the config stores the edge on the tool side.
        self.agent_tools: dict[str, list[str]] = {}
        for n in cfg["nodes"]:
            if n.get("type") == "tool":
                for a in n.get("connects", []):
                    self.agent_tools.setdefault(a, []).append(n["id"])
        self._running = False

    @property
    def busy(self) -> bool:
        return self._running

    async def run_task(self, text: str) -> dict:
        if self._running:
            raise RuntimeError("orchestrator busy")
        self._running = True
        rec = store.new_task(title=text.strip()[:80] or "Untitled task")
        try:
            await self.b.broadcast(CoreStateEvent(state="orchestrating"))
            plan = await self._plan(text)
            await self.b.broadcast(TaskCreated(id=rec.id, title=rec.title, assignee=plan[0][0]))
            await self.b.broadcast(TaskUpdate(id=rec.id, state="running"))
            await self._log(rec, None, f"Manager delegating to: {', '.join(r for r, _ in plan)}")

            outputs = await asyncio.gather(
                *(self._run_agent(rec, role, sub) for role, sub in plan)
            )
            answer = await self._synthesize(rec, text, plan, outputs)
            rec.output = answer
            rec.state = "done"
            await self.b.broadcast(TaskUpdate(id=rec.id, state="done", output=answer))
            await self.b.broadcast(LogEvent(level="info", msg=f"Task {rec.id} complete"))
            return store.detail(rec.id)  # type: ignore[return-value]
        except Exception as exc:
            rec.state = "failed"
            await self.b.broadcast(TaskUpdate(id=rec.id, state="failed", output=str(exc)))
            await self.b.broadcast(LogEvent(level="error", msg=f"Task {rec.id} failed: {exc}"))
            raise
        finally:
            await self.b.broadcast(CoreStateEvent(state="standby"))
            store.save()
            self._running = False

    # ── planning ──
    async def _plan(self, text: str) -> List[Tuple[str, str]]:
        if self.provider.is_real:
            try:
                return await self._plan_llm(text)
            except Exception:
                pass  # fall back to heuristic
        return self._plan_heuristic(text)

    def _plan_heuristic(self, text: str) -> List[Tuple[str, str]]:
        low = text.lower()
        chosen: List[str] = []
        for kw, role in _KEYWORDS.items():
            if kw in low and role not in chosen:
                chosen.append(role)
        if not chosen:
            chosen = ["strategist", "researcher"]
        chosen = chosen[:3]
        return [(r, text.strip()) for r in chosen]

    async def _plan_llm(self, text: str) -> List[Tuple[str, str]]:
        roster = "\n".join(f"- {rid}: {r.get('role','')}" for rid, r in self.roles.items())
        system = (
            "You are the manager of a team of AI role-agents. Choose the 1-3 most "
            "relevant agents for the user's request and give each a focused subtask.\n"
            "Reply ONLY with a JSON array like "
            '[{"role":"researcher","subtask":"..."}]. Use exact role ids from the list.'
        )
        raw = await self.provider.complete(system, f"Agents:\n{roster}\n\nRequest: {text}", max_tokens=400)
        m = re.search(r"\[.*\]", raw, re.S)
        data = json.loads(m.group(0) if m else raw)
        plan = [(d["role"], d.get("subtask", text)) for d in data if d.get("role") in self.roles]
        return plan[:3] or self._plan_heuristic(text)

    # ── per-agent execution ──
    async def _run_agent(self, rec: TaskRecord, role: str, subtask: str) -> str:
        ar = rec.agent(role)
        await self._status(rec, role, "thinking")
        await self.b.broadcast(EdgeActive(**{"from": self.core_id}, to=role, on=True))
        await self._log(rec, role, f"Received subtask: {subtask[:120]}")

        context = await self._use_tools(rec, role, subtask)
        await self._status(rec, role, "working")

        role_def = self.roles[role]
        system = (
            f"You are the {role_def['label']} agent. {role_def.get('role','')}\n"
            "Be concise and practical. Return a short, useful result."
        )
        prompt = subtask if not context else f"{subtask}\n\nContext from your tools:\n{context}"
        try:
            out = await self.provider.complete(system, prompt, max_tokens=600)
        except Exception as exc:
            await self._status(rec, role, "error")
            ar.log(f"LLM error: {exc}")
            await self.b.broadcast(EdgeActive(**{"from": self.core_id}, to=role, on=False))
            return f"[{role} failed: {exc}]"

        ar.output = out
        ar.log("Produced result.")

        # Memory-connected agents persist their finding for future runs.
        if "memory" in self.agent_tools.get(role, []):
            await self._tool(rec, role, "memory", "store",
                             {"text": f"{role}: {out[:400]}", "meta": {"task": rec.id, "role": role}})

        await self._status(rec, role, "done")
        await self.b.broadcast(EdgeActive(**{"from": self.core_id}, to=role, on=False))
        await asyncio.sleep(0.15)
        await self._status(rec, role, "idle")
        return out

    async def _use_tools(self, rec: TaskRecord, role: str, subtask: str) -> str:
        """Call the role's connected tools; return a text digest for the prompt."""
        bits: List[str] = []
        for tool in self.agent_tools.get(role, []):
            if tool not in self.connectors:
                continue
            if tool == "memory":
                res = await self._tool(rec, role, "memory", "recall", {"query": subtask, "k": 2})
                hits = res.get("hits", [])
                if hits:
                    bits.append("memory: " + "; ".join(h["text"][:80] for h in hits))
                continue
            action = {"email": "search", "calendar": "list_events", "drive": "search"}.get(tool, "call")
            res = await self._tool(rec, role, tool, action, {"query": subtask})
            bits.append(f"{tool}: {json.dumps(res)[:200]}")
        return "\n".join(bits)

    async def _tool(self, rec: TaskRecord, role: str, tool: str, action: str, params: dict) -> dict:
        await self.b.broadcast(EdgeActive(**{"from": role}, to=tool, on=True))
        await self.b.broadcast(ToolCall(node=tool, action=action, summary=f"{role} → {tool}.{action}"))
        try:
            res = await self.connectors[tool].call(action, **params)
            ok, summary = True, f"{tool}.{action} ok"
        except Exception as exc:
            res, ok, summary = {"error": str(exc)}, False, f"{tool}.{action} failed"
        rec.agent(role).tools.append({"ts": _now(), "node": tool, "action": action, "ok": ok, "summary": summary})
        await self.b.broadcast(ToolResult(node=tool, action=action, ok=ok, summary=summary))
        await self.b.broadcast(EdgeActive(**{"from": role}, to=tool, on=False))
        return res

    # ── synthesis ──
    async def _synthesize(self, rec: TaskRecord, text: str, plan, outputs) -> str:
        combined = "\n\n".join(f"### {role}\n{out}" for (role, _), out in zip(plan, outputs))
        system = (
            "You are the lead orchestrator. Synthesize the agents' results into one "
            "clear, actionable answer for the user. Be concise."
        )
        try:
            return await self.provider.complete(system, f"Request: {text}\n\nAgent results:\n{combined}", max_tokens=700)
        except Exception:
            return combined  # graceful: return raw agent outputs if synthesis fails

    # ── event + record helpers ──
    async def _status(self, rec: TaskRecord, role: str, state: str) -> None:
        rec.agent(role).state = state
        await self.b.broadcast(AgentStatus(node=role, state=state))  # type: ignore[arg-type]

    async def _log(self, rec: TaskRecord, role: str | None, msg: str) -> None:
        if role:
            rec.agent(role).log(msg)
        await self.b.broadcast(LogEvent(level="info", msg=msg, node=role))


def _now() -> int:
    from .events import now_ms
    return now_ms()
