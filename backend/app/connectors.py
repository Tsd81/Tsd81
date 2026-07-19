"""Tool/data connectors behind one interface (the outer graph nodes).

Each connector maps to an outer 'tool' node. Calling one emits tool.call →
tool.result events (lighting the node) and returns structured data the agent
folds into its answer.

Phase 4: these return realistic MOCK data through a real, stable interface.
Phase 5: swap the body of each `call()` for a real MCP client / API call —
the interface, events, and graph wiring stay identical.

Memory is backed by Qdrant when reachable, else an in-memory store, so it
works with or without the vector DB running.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Protocol

import httpx


class Connector(Protocol):
    node: str
    async def call(self, action: str, **params: Any) -> Dict[str, Any]: ...


# ── Mock tool connectors ──────────────────────────────────────────────
class EmailConnector:
    node = "email"

    async def call(self, action: str, **params: Any) -> Dict[str, Any]:
        q = params.get("query", "")
        if action == "search":
            return {"matches": [
                {"from": "anna@acme.com", "subject": f"Re: {q or 'proposal'}", "snippet": "Sounds good, let's proceed."},
                {"from": "billing@vendor.io", "subject": "Invoice #4821 due", "snippet": "Payment due in 5 days."},
            ]}
        if action == "send":
            return {"sent": True, "to": params.get("to", "someone@example.com")}
        return {"threads": 12, "unread": 3}


class CalendarConnector:
    node = "calendar"

    async def call(self, action: str, **params: Any) -> Dict[str, Any]:
        if action in ("list_events", "find_slot"):
            return {"events": [
                {"title": "Standup", "time": "09:30", "duration_min": 15},
                {"title": "Design review", "time": "14:00", "duration_min": 45},
            ], "next_free": "16:00–17:00"}
        if action == "create_event":
            return {"created": True, "title": params.get("title", "New event")}
        return {"today": 2}


class DriveConnector:
    node = "drive"

    async def call(self, action: str, **params: Any) -> Dict[str, Any]:
        q = params.get("query", "")
        if action in ("search", "list"):
            return {"files": [
                {"name": f"{(q or 'notes').title()}.md", "modified": "2d ago", "size": "14 KB"},
                {"name": "Q3-plan.docx", "modified": "1w ago", "size": "82 KB"},
            ]}
        if action == "read_file":
            return {"name": params.get("name", "doc.md"),
                    "content": "## Summary\n- Point A\n- Point B\n- Next steps outlined."}
        return {"files": 128}


# ── Memory connector (Qdrant with in-memory fallback) ─────────────────
class MemoryConnector:
    node = "memory"

    def __init__(self) -> None:
        self._url = os.getenv("QDRANT_URL", "").strip()
        self._collection = "orchestrator_memory"
        self._mem: List[Dict[str, Any]] = []  # in-memory fallback
        self._qdrant_ok: Optional[bool] = None

    def _embed(self, text: str, dim: int = 64) -> List[float]:
        # Deterministic hashing "embedding" — no model needed, good enough for
        # a demo similarity. Swap for a real embedder in Phase 5.
        vec = [0.0] * dim
        for i, tok in enumerate(text.lower().split()):
            vec[hash(tok) % dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    async def call(self, action: str, **params: Any) -> Dict[str, Any]:
        if action == "store":
            return await self._store(params.get("text", ""), params.get("meta", {}))
        if action in ("recall", "search"):
            return await self._recall(params.get("query", ""), int(params.get("k", 3)))
        return {"count": len(self._mem)}

    async def _store(self, text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        entry = {"text": text, "meta": meta, "vec": self._embed(text)}
        if await self._try_qdrant_upsert(entry):
            return {"stored": True, "backend": "qdrant"}
        self._mem.append(entry)
        return {"stored": True, "backend": "memory"}

    async def _recall(self, query: str, k: int) -> Dict[str, Any]:
        qvec = self._embed(query)
        hits = await self._try_qdrant_search(qvec, k)
        if hits is not None:
            return {"hits": hits, "backend": "qdrant"}
        # in-memory cosine
        scored = sorted(
            ({"text": e["text"], "meta": e["meta"],
              "score": sum(a * b for a, b in zip(qvec, e["vec"]))}
             for e in self._mem),
            key=lambda h: h["score"], reverse=True,
        )
        return {"hits": scored[:k], "backend": "memory"}

    async def _try_qdrant_upsert(self, entry: Dict[str, Any]) -> bool:
        if not self._url:
            return False
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                await self._ensure_collection(c, len(entry["vec"]))
                pid = abs(hash(entry["text"])) % (10 ** 12)
                await c.put(
                    f"{self._url}/collections/{self._collection}/points",
                    json={"points": [{"id": pid, "vector": entry["vec"],
                                      "payload": {"text": entry["text"], "meta": entry["meta"]}}]},
                )
            return True
        except Exception:
            return False

    async def _try_qdrant_search(self, qvec: List[float], k: int) -> Optional[List[dict]]:
        if not self._url:
            return None
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.post(
                    f"{self._url}/collections/{self._collection}/points/search",
                    json={"vector": qvec, "limit": k, "with_payload": True},
                )
                r.raise_for_status()
                res = r.json().get("result", [])
                return [{"text": h["payload"].get("text", ""),
                         "meta": h["payload"].get("meta", {}),
                         "score": h.get("score", 0)} for h in res]
        except Exception:
            return None

    async def _ensure_collection(self, c: httpx.AsyncClient, dim: int) -> None:
        try:
            r = await c.get(f"{self._url}/collections/{self._collection}")
            if r.status_code == 200:
                return
        except Exception:
            pass
        await c.put(f"{self._url}/collections/{self._collection}",
                    json={"vectors": {"size": dim, "distance": "Cosine"}})


_REGISTRY: Dict[str, Connector] = {}


def get_connectors() -> Dict[str, Connector]:
    global _REGISTRY
    if not _REGISTRY:
        for conn in (EmailConnector(), CalendarConnector(), DriveConnector(), MemoryConnector()):
            _REGISTRY[conn.node] = conn
    return _REGISTRY
