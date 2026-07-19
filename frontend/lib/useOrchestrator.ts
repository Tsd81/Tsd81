"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BACKEND_WS } from "./config";
import type {
  AgentState,
  CoreState,
  LogEvent,
  OrchestratorEvent,
} from "./events";

export interface Task {
  id: string;
  title: string;
  assignee: string;
  state: "running" | "done" | "failed";
  output?: string;
}

export interface OrchestratorState {
  connected: boolean;
  core: CoreState;
  nodes: Record<string, AgentState>;
  activeEdges: Set<string>; // "from->to"
  logs: LogEvent[];
  tasks: Record<string, Task>;
}

const edgeKey = (from: string, to: string) => `${from}->${to}`;

const initialState: OrchestratorState = {
  connected: false,
  core: "standby",
  nodes: {},
  activeEdges: new Set(),
  logs: [],
  tasks: {},
};

/**
 * Subscribes to the backend WebSocket, reduces the event stream into render
 * state, and reconnects with exponential backoff on drop.
 */
export function useOrchestrator(): OrchestratorState {
  const [state, setState] = useState<OrchestratorState>(initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const closedRef = useRef(false);

  const reduce = useCallback((ev: OrchestratorEvent) => {
    setState((s) => {
      switch (ev.type) {
        case "snapshot": {
          const activeEdges = new Set(
            ev.edges.map((e) => edgeKey(e.from, e.to))
          );
          return { ...s, core: ev.core, nodes: { ...ev.nodes }, activeEdges };
        }
        case "agent.status":
          return { ...s, nodes: { ...s.nodes, [ev.node]: ev.state } };
        case "core.state":
          return { ...s, core: ev.state };
        case "edge.active": {
          const activeEdges = new Set(s.activeEdges);
          const k = edgeKey(ev.from, ev.to);
          if (ev.on) activeEdges.add(k);
          else activeEdges.delete(k);
          return { ...s, activeEdges };
        }
        case "tool.call":
          // Light the tool node as "working" while a call is in flight.
          return { ...s, nodes: { ...s.nodes, [ev.node]: "working" } };
        case "tool.result":
          return {
            ...s,
            nodes: { ...s.nodes, [ev.node]: ev.ok ? "idle" : "error" },
          };
        case "task.created":
          return {
            ...s,
            tasks: {
              ...s.tasks,
              [ev.id]: {
                id: ev.id,
                title: ev.title,
                assignee: ev.assignee,
                state: "running",
              },
            },
          };
        case "task.update":
          return {
            ...s,
            tasks: {
              ...s.tasks,
              [ev.id]: {
                ...(s.tasks[ev.id] ?? {
                  id: ev.id,
                  title: ev.id,
                  assignee: "",
                }),
                state: ev.state,
                output: ev.output ?? s.tasks[ev.id]?.output,
              },
            },
          };
        case "log":
          return { ...s, logs: [...s.logs.slice(-199), ev] };
        default:
          return s;
      }
    });
  }, []);

  useEffect(() => {
    closedRef.current = false;

    const connect = () => {
      if (closedRef.current) return;
      const ws = new WebSocket(BACKEND_WS);
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setState((s) => ({ ...s, connected: true }));
      };
      ws.onmessage = (e) => {
        try {
          reduce(JSON.parse(e.data) as OrchestratorEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (closedRef.current) return;
        const delay = Math.min(1000 * 2 ** retryRef.current, 8000);
        retryRef.current += 1;
        setTimeout(connect, delay);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closedRef.current = true;
      wsRef.current?.close();
    };
  }, [reduce]);

  return state;
}
