"""Loads the shared nodes.config.json (single source of truth for the graph)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


def _config_path() -> Path:
    # Allow override via env; default to repo-root nodes.config.json.
    override = os.getenv("NODES_CONFIG_PATH")
    if override:
        return Path(override)
    # backend/app/nodes.py -> repo root is two levels up from app/.
    return Path(__file__).resolve().parents[2] / "nodes.config.json"


@lru_cache(maxsize=1)
def load_nodes_config() -> Dict[str, Any]:
    path = _config_path()
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def node_ids() -> list[str]:
    cfg = load_nodes_config()
    return [n["id"] for n in cfg["nodes"]]


def agent_ids() -> list[str]:
    cfg = load_nodes_config()
    return [n["id"] for n in cfg["nodes"] if n.get("type") == "agent"]


def tool_ids() -> list[str]:
    cfg = load_nodes_config()
    return [n["id"] for n in cfg["nodes"] if n.get("type") == "tool"]
