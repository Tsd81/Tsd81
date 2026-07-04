# AI Orchestrator Dashboard

A real, working personal AI orchestrator with a live dashboard. A central
glowing **core** (the lead agent) radiates curved links to role agents
(inner ring) and tool/data connectors (outer ring). When an agent works, its
node pulses and the link to the core animates — **driven by a live event
stream, not a canned animation.**

> **Status: Phase 1 complete** — reference-quality visuals + real weather HUD.
> The graph is real and driven by the WebSocket; the core pulses, active edges
> flow teal particles, nodes glow on state change, and the HUD shows real
> weather. The *content* of the events is still faked on a loop (replaced by the
> real CrewAI orchestrator in Phase 2).

---

## Run it (non-technical operator)

You need **Docker Desktop** installed and running. Then, in a terminal:

```bash
# 1. (optional) copy the env template — not required for Phase 0
cp .env.example .env

# 2. start everything (qdrant + backend + frontend)
docker compose up --build
```

Wait until you see the frontend and backend logs settle, then open:

**http://localhost:3000**

You should see the dashboard: the orange core in the middle, ~16 nodes
around it, and nodes/links lighting up live as the (currently simulated)
orchestrator runs tasks. The little dot top-left says **live** when the
dashboard is connected to the backend.

To stop: press `Ctrl+C`, then `docker compose down`.

### Run without Docker (developers)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
NODES_CONFIG_PATH=../nodes.config.json uvicorn app.main:app --reload --port 8000
```
Frontend (in another terminal):
```bash
cd frontend
npm install
npm run dev
# open http://localhost:3000
```

---

## What's real vs. still mocked (Phase 1)

| Piece | State |
|---|---|
| Monorepo, docker-compose, env, READMEs | ✅ real |
| `nodes.config.json` — single source of truth for the graph | ✅ real |
| Event contract (`contract/events.schema.json` ↔ Pydantic ↔ TS types) | ✅ real |
| WebSocket stream + snapshot-on-connect + reconnect | ✅ real |
| Frontend graph rendered from `nodes.config.json`, lit purely by the socket | ✅ real |
| Pulsing core, particle-flow on active edges, node glow states | ✅ real |
| HUD: live clock, greeting, day-rotating history line | ✅ real |
| Weather — real free API (Open-Meteo, no key), timeout/retry/cache/fallback | ✅ real |
| Reduced-motion / low-end-device graceful degradation | ✅ real |
| **Content** of the events (which agent, what task) | 🟡 faked on a loop |
| CrewAI agents, MCP tools, Qdrant memory | ⏳ Phases 2–5 |

> **Weather note:** uses [Open-Meteo](https://open-meteo.com) — free, no API key.
> Set the city via `WEATHER_CITY` (or `WEATHER_LAT`/`WEATHER_LON`) in `.env`.
> If the network can't reach the API, the HUD shows "unavailable" and everything
> else keeps working — the graph never freezes on a failed external call.

---

## Architecture

```
/backend            FastAPI + WebSocket. Phase 0: fake event loop.
  app/events.py     Pydantic event models (mirror the contract schema)
  app/nodes.py      Loads nodes.config.json
  app/broadcaster.py WS connection manager + authoritative runtime state
  app/fake_loop.py  Phase-0 event generator (deleted/replaced in Phase 2)
  app/main.py       App: /ws, /api/nodes, /api/hud, /api/health
/frontend           Next.js + TS + Tailwind + React Flow + Framer Motion
  lib/events.ts     TS types (mirror the contract schema)
  lib/useOrchestrator.ts  WS hook → reduces events into render state
  lib/layout.ts     Radial node placement from ring + angle
  components/        Graph, CoreNode, OrbNode, Hud, Dashboard
/mcp                Mock MCP servers (Phase 4)
/contract           events.schema.json — single source of truth for events
nodes.config.json   Single source of truth for the graph (backend serves it)
docker-compose.yml  qdrant + backend + frontend, one command
```

### The event contract (the spine)

The backend emits JSON events over `ws://localhost:8000/ws`; the frontend
renders them. Both sides derive their types from
[`contract/events.schema.json`](contract/events.schema.json). Event types:
`snapshot`, `agent.status`, `tool.call`, `tool.result`, `edge.active`,
`task.created`, `task.update`, `core.state`, `log`.

On connect, the backend immediately sends a `snapshot` of current state so a
refreshed or late-joining dashboard renders correctly without waiting for the
next event.

### Nodes

Every node lives in `nodes.config.json` (id, label, ring, type, angle). The
backend serves it at `GET /api/nodes`; the frontend fetches it and lays out
the graph deterministically. Changing the roster in one file updates both
the runtime and the visual — they can't drift.

---

## Phase roadmap

- **Phase 0 — Skeleton + contract** ✅
- **Phase 1 — Reference-quality visuals + real weather HUD** ✅ *(this build)*
- Phase 2 — Real CrewAI orchestrator, one role end-to-end (Researcher)
- Phase 3 — All role agents + real delegation + per-node panels
- Phase 4 — Tools via MCP (mock protocol) + Qdrant memory
- Phase 5 — Real connectors (Gmail/Calendar/Drive) + hardening
