"use client";

import { useEffect, useState } from "react";
import { BACKEND_HTTP } from "@/lib/config";
import type { NodesConfig } from "@/lib/events";
import type { OrchestratorState } from "@/lib/useOrchestrator";

interface AgentDetail {
  state: string;
  logs: { ts: number; msg: string }[];
  tools: { ts: number; node: string; action: string; ok: boolean; summary: string }[];
  output: string;
}

export function NodePanel({
  nodeId,
  cfg,
  state,
  onClose,
}: {
  nodeId: string;
  cfg: NodesConfig;
  state: OrchestratorState;
  onClose: () => void;
}) {
  const def =
    nodeId === cfg.core.id
      ? { label: cfg.core.label, role: "Lead orchestrator", type: "manager" }
      : cfg.nodes.find((n) => n.id === nodeId);
  const [detail, setDetail] = useState<AgentDetail | null>(null);

  // Fetch the latest task's record for this agent (output + persisted logs).
  // Re-fetch when the core returns to standby (a run just finished).
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const list = await fetch(`${BACKEND_HTTP}/api/tasks`).then((r) => r.json());
        const latest = list.tasks?.[0];
        if (!latest) return;
        const d = await fetch(`${BACKEND_HTTP}/api/tasks/${latest.id}`).then((r) => r.json());
        if (!cancelled) setDetail(d.agents?.[nodeId] ?? null);
      } catch {
        /* ignore */
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [nodeId, state.core]);

  const liveLogs = state.logs.filter((l) => l.node === nodeId).slice(-8);
  const nodeState = state.nodes[nodeId] ?? (nodeId === cfg.core.id ? state.core : "idle");

  return (
    <div className="absolute top-6 right-6 z-20 w-[340px] max-h-[80vh] overflow-y-auto rounded-xl border border-white/15 bg-black/70 backdrop-blur p-4 text-sm shadow-xl">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-white font-semibold">{def?.label ?? nodeId}</div>
          <div className="text-[11px] text-white/45 capitalize">
            {(def as any)?.type ?? "node"} · {nodeState}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-white/40 hover:text-white text-lg leading-none"
          aria-label="Close panel"
        >
          ×
        </button>
      </div>

      {"role" in (def ?? {}) && (def as any).role && (
        <p className="mt-2 text-xs text-white/55">{(def as any).role}</p>
      )}

      {/* Live log lines routed to this node */}
      {liveLogs.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-white/35 mb-1">Live</div>
          <div className="space-y-0.5">
            {liveLogs.map((l, i) => (
              <div key={i} className="text-xs text-accent/80 truncate">{l.msg}</div>
            ))}
          </div>
        </div>
      )}

      {detail?.tools?.length ? (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-white/35 mb-1">Tool calls</div>
          <div className="space-y-0.5">
            {detail.tools.map((t, i) => (
              <div key={i} className="text-xs text-white/60">
                <span className={t.ok ? "text-emerald-400" : "text-red-400"}>●</span>{" "}
                {t.node}.{t.action}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {detail?.output ? (
        <div className="mt-3">
          <div className="text-[10px] uppercase tracking-wider text-white/35 mb-1">Output</div>
          <pre className="text-xs text-white/80 whitespace-pre-wrap font-sans">{detail.output}</pre>
        </div>
      ) : (
        <div className="mt-3 text-xs text-white/35">
          No output yet — submit a task and click this node during a run.
        </div>
      )}
    </div>
  );
}
