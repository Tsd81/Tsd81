"""In-memory task/agent run store with optional JSON persistence.

Survives a backend restart (Phase 5) by snapshotting to a file. Exposes the
data the side panels render: per-task metadata, per-agent live logs + output.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .events import now_ms


@dataclass
class AgentRun:
    node: str
    state: str = "idle"           # idle|thinking|working|done|error
    logs: List[dict] = field(default_factory=list)  # {ts, msg}
    tools: List[dict] = field(default_factory=list)  # {ts, node, action, ok, summary}
    output: str = ""

    def log(self, msg: str) -> None:
        self.logs.append({"ts": now_ms(), "msg": msg})


@dataclass
class TaskRecord:
    id: str
    title: str
    state: str = "running"        # running|done|failed
    created_ts: int = field(default_factory=now_ms)
    assignees: List[str] = field(default_factory=list)
    agents: Dict[str, AgentRun] = field(default_factory=dict)
    output: str = ""

    def agent(self, node: str) -> AgentRun:
        if node not in self.agents:
            self.agents[node] = AgentRun(node=node)
            if node not in self.assignees:
                self.assignees.append(node)
        return self.agents[node]


class TaskStore:
    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._tasks: Dict[str, TaskRecord] = {}
        self._seq = 0
        self._lock = threading.Lock()
        self._persist_path = persist_path or os.getenv("TASKS_PERSIST_PATH")
        self._load()

    def new_task(self, title: str) -> TaskRecord:
        with self._lock:
            self._seq += 1
            tid = f"t{self._seq}"
            rec = TaskRecord(id=tid, title=title)
            self._tasks[tid] = rec
            return rec

    def get(self, tid: str) -> Optional[TaskRecord]:
        return self._tasks.get(tid)

    def list(self) -> List[dict]:
        return [self._summary(t) for t in sorted(
            self._tasks.values(), key=lambda r: r.created_ts, reverse=True)]

    def detail(self, tid: str) -> Optional[dict]:
        rec = self._tasks.get(tid)
        return self._full(rec) if rec else None

    @staticmethod
    def _summary(rec: TaskRecord) -> dict:
        return {
            "id": rec.id, "title": rec.title, "state": rec.state,
            "created_ts": rec.created_ts, "assignees": rec.assignees,
        }

    @staticmethod
    def _full(rec: TaskRecord) -> dict:
        d = asdict(rec)
        return d

    # ── persistence ──
    def save(self) -> None:
        if not self._persist_path:
            return
        try:
            p = Path(self._persist_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {"seq": self._seq, "tasks": {k: asdict(v) for k, v in self._tasks.items()}}
            p.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass  # persistence is best-effort; never break a run

    def _load(self) -> None:
        if not self._persist_path or not Path(self._persist_path).exists():
            return
        try:
            data = json.loads(Path(self._persist_path).read_text(encoding="utf-8"))
            self._seq = data.get("seq", 0)
            for tid, td in data.get("tasks", {}).items():
                agents = {k: AgentRun(**v) for k, v in td.pop("agents", {}).items()}
                self._tasks[tid] = TaskRecord(**td, agents=agents)
        except Exception:
            self._tasks = {}
            self._seq = 0


store = TaskStore()
