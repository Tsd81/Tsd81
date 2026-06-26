"""WebSocket connection manager + in-memory runtime state.

Holds the current state of every node/edge/core so a freshly-connected
client can be sent a `snapshot` immediately and render correct state
instead of waiting for the next event.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Set, Tuple

from fastapi import WebSocket

from .events import Event, Snapshot, now_ms
from .nodes import node_ids


class RuntimeState:
    """Authoritative current state, updated as events are broadcast."""

    def __init__(self) -> None:
        self.core: str = "standby"
        self.nodes: Dict[str, str] = {nid: "idle" for nid in node_ids()}
        self.active_edges: Set[Tuple[str, str]] = set()

    def apply(self, event: Event) -> None:
        t = event.type
        if t == "agent.status":
            self.nodes[event.node] = event.state
        elif t == "core.state":
            self.core = event.state
        elif t == "edge.active":
            key = (event.from_, event.to)
            if event.on:
                self.active_edges.add(key)
            else:
                self.active_edges.discard(key)

    def snapshot(self) -> Snapshot:
        return Snapshot(
            core=self.core,  # type: ignore[arg-type]
            nodes=dict(self.nodes),  # type: ignore[arg-type]
            edges=[{"from": a, "to": b} for (a, b) in self.active_edges],
            ts=now_ms(),
        )


class Broadcaster:
    def __init__(self) -> None:
        self._connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        self.state = RuntimeState()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        # Send current state so the client renders correctly on (re)connect.
        await ws.send_text(self.state.snapshot().model_dump_json(by_alias=True))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast(self, event: Event) -> None:
        # Update authoritative state first, then fan out.
        self.state.apply(event)
        payload = event.model_dump_json(by_alias=True)
        async with self._lock:
            targets = list(self._connections)
        dead: List[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)


broadcaster = Broadcaster()
