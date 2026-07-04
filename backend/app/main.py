"""FastAPI app: serves the node config, weather/HUD stub, and the WS stream.

Phase 0: the WebSocket stream is driven by a fake event loop. The graph,
node config endpoint and contract are real and unchanged in later phases.
"""
from __future__ import annotations

import asyncio
import contextlib
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .broadcaster import broadcaster
from .fake_loop import fake_event_loop
from .nodes import load_nodes_config

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


@app.on_event("startup")
async def _startup() -> None:
    global _loop_task
    # Phase 0 driver. Disable with FAKE_LOOP=0 once the real orchestrator lands.
    if os.getenv("FAKE_LOOP", "1") != "0":
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
    return {"ok": True, "phase": 0}


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
