# AI Orchestrator Dashboard

A real, working personal AI orchestrator with a live dashboard. A central
glowing **core** (the lead agent) radiates curved links to role agents
(inner ring) and tool/data connectors (outer ring). When an agent works, its
node pulses and the link to the core animates — **driven by a live event
stream, not a canned animation.**

> **Status: Phases 0–4 (core) complete** — live graph, reference visuals, and a
> **real working orchestrator**. Type a request in the dashboard → a manager
> delegates to real role agents → each agent calls its tools and produces output
> → you get a synthesized answer, with the graph reflecting the actual run. Works
> **with or without** an API key (deterministic offline mock when no key is set).
>
> **Note on the agent framework:** the master prompt specified CrewAI. This build
> uses a **custom hierarchical orchestrator behind a swappable interface** instead,
> because (a) event emission needs fine-grained control and (b) a CrewAI run can't
> be verified in the build sandbox without an API key. The LLM provider and the
> orchestrator both sit behind interfaces, so a CrewAI adapter can drop in without
> touching the graph, contract, or frontend. Say the word and I'll switch to CrewAI.

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

You'll see the dashboard: the orange core in the middle, ~16 nodes around it,
and the **task bar at the bottom**. Type a request — e.g. *"Research competitors
and check the calendar for a meeting slot"* — and press **Run**. Watch the core
switch to ORCHESTRATING, the relevant agents light up, their tool nodes (Email,
Calendar, Drive, Memory) flash as they're called, and a synthesized answer come
back. **Click any node** to open a side panel with its live log, tool calls, and
output.

Without an `ANTHROPIC_API_KEY`, agents return deterministic **mock** output but
everything else is real (routing, delegation, tools, memory, events). Add your
key to `.env` (`ANTHROPIC_API_KEY=...`) to get real Claude answers.

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

## What's real vs. still mocked (Phases 0–4)

| Piece | State |
|---|---|
| Monorepo, docker-compose, env, READMEs | ✅ real |
| `nodes.config.json` + event contract (schema ↔ Pydantic ↔ TS) | ✅ real |
| WebSocket stream + snapshot-on-connect + reconnect | ✅ real |
| Graph rendered from config, lit purely by the socket | ✅ real |
| Pulsing core, particle-flow edges, node glow, reduced-motion degradation | ✅ real |
| Weather — real free API (Open-Meteo), timeout/retry/cache/fallback | ✅ real |
| **Orchestrator**: manager routing + delegation + fan-out to 1–3 agents | ✅ real |
| All 13 role agents with distinct system prompts | ✅ real |
| `/api/task` end-to-end run emitting real contract events | ✅ real |
| Clickable node → side panel with live log, tool calls, output | ✅ real |
| Task persistence (survives restart) + `/api/tasks` history | ✅ real |
| LLM provider — **real Claude** (Anthropic SDK) when key set | ✅ real |
| LLM provider — deterministic **offline mock** when no key | ✅ real (fallback) |
| Tools (Email/Calendar/Drive) — realistic data behind a stable interface | 🟡 mock data, real interface + events |
| Memory — Qdrant-backed when reachable, else in-memory | 🟡 real store; hash "embeddings" (swap for real embedder) |
| Agent framework | 🟡 custom orchestrator (CrewAI swap available on request) |
| MCP wire protocol, real Gmail/Calendar/Drive connectors, auth | ⏳ Phase 5 |

> **Weather note:** uses [Open-Meteo](https://open-meteo.com) — free, no API key.
> Set the city via `WEATHER_CITY` (or `WEATHER_LAT`/`WEATHER_LON`) in `.env`.
> If the network can't reach the API, the HUD shows "unavailable" and everything
> else keeps working — the graph never freezes on a failed external call.

---

## Architecture

```
/backend            FastAPI + WebSocket + orchestrator
  app/events.py     Pydantic event models (mirror the contract schema)
  app/nodes.py      Loads nodes.config.json
  app/broadcaster.py WS connection manager + authoritative runtime state
  app/llm.py        Swappable LLM provider (Anthropic real + offline mock)
  app/connectors.py Tool/data connectors (Email/Calendar/Drive/Memory)
  app/orchestrator.py  Manager → delegation → agents → tools → synthesis
  app/tasks.py      Task/agent run store (+ JSON persistence)
  app/fake_loop.py  Optional demo-mode event generator (DEMO_MODE=1)
  app/weather.py    Real weather via Open-Meteo
  app/main.py       App: /ws, /api/task, /api/tasks, /api/nodes, /api/hud
/frontend           Next.js + TS + Tailwind + React Flow + Framer Motion
  lib/events.ts     TS types (mirror the contract schema)
  lib/useOrchestrator.ts  WS hook → reduces events into render state
  lib/layout.ts     Radial node placement from ring + angle
  components/        Graph, CoreNode, OrbNode, FlowEdge, Hud, TaskBar,
                     NodePanel, Dashboard
/mcp                Mock connector notes (real MCP wire protocol: Phase 5)
/contract           events.schema.json — single source of truth for events
nodes.config.json   Single source of truth for the graph (backend serves it)
docker-compose.yml  qdrant + backend + frontend, one command
```

### How a task runs

1. `POST /api/task {text}` → `core.state: orchestrating`.
2. **Manager routing** picks 1–3 agents (LLM-based when a real key is set,
   deterministic keyword routing otherwise).
3. Chosen agents run **in parallel**; each calls its connected tools (emitting
   `tool.call`/`tool.result`, lighting the outer nodes), recalls/stores memory,
   then produces output via the LLM provider.
4. The manager **synthesizes** one answer; `core.state: standby`.
5. Every step emits real contract events, so the graph is a live mirror of the
   run. Everything is recorded in the TaskStore for the side panels.

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
- **Phase 1 — Reference-quality visuals + real weather HUD** ✅
- **Phase 2 — Real orchestrator, one role end-to-end** ✅
- **Phase 3 — All role agents + real delegation + per-node panels** ✅
- **Phase 4 — Tools + memory (mock data, real interface & events)** ✅ core
- Phase 5 — Real MCP wire protocol / connectors (Gmail/Calendar/Drive),
  auth on the dashboard, richer error surfacing *(partial: retries, reconnect,
  error node states, and task persistence are already in)*
