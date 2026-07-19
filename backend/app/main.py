"""FastAPI app: serves the node config, weather/HUD stub, and the WS stream.

Phase 0: the WebSocket stream is driven by a fake event loop. The graph,
node config endpoint and contract are real and unchanged in later phases.
"""
from __future__ import annotations

import asyncio
import contextlib
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .broadcaster import broadcaster
from .crew import CrewOrchestrator
from .fake_loop import fake_event_loop
from .llm import get_provider
from .nodes import load_nodes_config
from .tasks import store

app = FastAPI(title="AI Orchestrator Dashboard — Backend", version="0.1.0")

# CORS so the Next.js dev server / container can call the HTTP endpoints.
_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_loop_task: asyncio.Task | None = None
# CrewAI when a real key is present; custom offline orchestrator otherwise.
orchestrator = CrewOrchestrator(broadcaster)


@app.on_event("startup")
async def _startup() -> None:
    global _loop_task
    # Demo mode replays fake lifecycle events so the graph is lively with no
    # task submitted. Off by default now that the real orchestrator exists.
    if os.getenv("DEMO_MODE", "0") == "1":
        _loop_task = asyncio.create_task(fake_event_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _loop_task
    if _loop_task:
        _loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _loop_task


@app.get("/api/health")
async def health() -> dict:
    prov = get_provider()
    return {"ok": True, "phase": 3, "llm": prov.name, "llm_real": prov.is_real,
            "engine": orchestrator.engine, "busy": orchestrator.busy}


class TaskRequest(BaseModel):
    text: str


@app.post("/api/task")
async def create_task(req: TaskRequest) -> dict:
    """Submit a request → manager delegates to role agents → real answer.
    Emits the full contract event stream, so the graph reflects the run."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if orchestrator.busy:
        raise HTTPException(status_code=409, detail="orchestrator busy; try again shortly")
    try:
        return await orchestrator.run_task(text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/tasks")
async def list_tasks() -> dict:
    return {"tasks": store.list()}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    detail = store.detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="task not found")
    return detail


@app.get("/api/nodes")
async def nodes() -> dict:
    """Single source of truth for the graph — frontend fetches this."""
    return load_nodes_config()


_HISTORY_LINES = [
    "1969 — ARPANET's first node specs circulated, a seed of the internet.",
    "1971 — Ray Tomlinson sent the first networked email, choosing '@'.",
    "1991 — The first website went live at CERN.",
    "2007 — The smartphone era began, putting agents in every pocket.",
    "1950 — Turing asked 'Can machines think?' in Computing Machinery and Intelligence.",
    "1956 — The Dartmouth workshop coined the term 'artificial intelligence'.",
    "1997 — Deep Blue beat world champion Garry Kasparov at chess.",
]


@app.get("/api/hud")
async def hud() -> dict:
    """HUD data: greeting, real weather, one 'this day' history line."""
    import datetime

    from .weather import get_weather

    now = datetime.datetime.now()
    hour = now.hour
    greeting = (
        "Good morning" if hour < 12 else
        "Good afternoon" if hour < 18 else
        "Good evening"
    )
    city = os.getenv("WEATHER_CITY", "Sofia")
    weather = await get_weather(city)  # None on failure → frontend shows fallback
    # Deterministic per-day rotation (no randomness → stable across a day).
    history = _HISTORY_LINES[now.timetuple().tm_yday % len(_HISTORY_LINES)]
    return {
        "greeting": greeting,
        "history": history,
        "city": city,
        "weather": weather,
    }


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await broadcaster.connect(websocket)
    try:
        while True:
            # We don't expect client messages in Phase 0, but keep the socket
            # alive and drain anything the client sends (e.g. pings).
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)
