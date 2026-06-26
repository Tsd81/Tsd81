"use client";

import { useEffect, useState } from "react";
import { BACKEND_HTTP } from "@/lib/config";
import type { NodesConfig } from "@/lib/events";
import { useOrchestrator } from "@/lib/useOrchestrator";
import { Graph } from "./Graph";
import { Hud } from "./Hud";

export function Dashboard() {
  const [cfg, setCfg] = useState<NodesConfig | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const state = useOrchestrator();

  useEffect(() => {
    fetch(`${BACKEND_HTTP}/api/nodes`)
      .then((r) => r.json())
      .then(setCfg)
      .catch(() => setErr("Cannot reach backend at " + BACKEND_HTTP));
  }, []);

  const activeCount = Object.values(state.nodes).filter(
    (s) => s === "working" || s === "thinking"
  ).length;
  const lastLog = state.logs[state.logs.length - 1];

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#0a0d14] text-white">
      <Hud connected={state.connected} />

      {/* Top-right status */}
      <div className="absolute top-6 right-6 z-10 text-right text-xs text-white/50 space-y-1">
        <div>
          core:{" "}
          <span className={state.core === "orchestrating" ? "text-accent" : ""}>
            {state.core}
          </span>
        </div>
        <div>active agents: {activeCount}</div>
        {lastLog && (
          <div className="max-w-xs text-white/40 truncate">{lastLog.msg}</div>
        )}
      </div>

      {!cfg && (
        <div className="absolute inset-0 flex items-center justify-center text-white/50">
          {err ?? "Loading graph…"}
        </div>
      )}

      {cfg && <Graph cfg={cfg} state={state} />}
    </main>
  );
}
