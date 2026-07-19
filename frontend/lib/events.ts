// TypeScript types for the WebSocket event contract.
// Source of truth: ../../contract/events.schema.json
// Keep in sync with backend/app/events.py.

export type AgentState = "idle" | "thinking" | "working" | "done" | "error";
export type CoreState = "standby" | "orchestrating";
export type TaskState = "running" | "done" | "failed";
export type LogLevel = "info" | "warn" | "error";

export interface AgentStatusEvent {
  type: "agent.status";
  node: string;
  state: AgentState;
  ts: number;
}
export interface ToolCallEvent {
  type: "tool.call";
  node: string;
  action: string;
  summary?: string;
  ts: number;
}
export interface ToolResultEvent {
  type: "tool.result";
  node: string;
  action: string;
  ok: boolean;
  summary?: string;
  ts: number;
}
export interface EdgeActiveEvent {
  type: "edge.active";
  from: string;
  to: string;
  on: boolean;
  ts: number;
}
export interface TaskCreatedEvent {
  type: "task.created";
  id: string;
  title: string;
  assignee: string;
  ts: number;
}
export interface TaskUpdateEvent {
  type: "task.update";
  id: string;
  state: TaskState;
  output?: string;
  ts: number;
}
export interface CoreStateEvent {
  type: "core.state";
  state: CoreState;
  ts: number;
}
export interface LogEvent {
  type: "log";
  level: LogLevel;
  msg: string;
  node?: string;
  ts: number;
}
export interface SnapshotEvent {
  type: "snapshot";
  core: CoreState;
  nodes: Record<string, AgentState>;
  edges: { from: string; to: string }[];
  ts: number;
}

export type OrchestratorEvent =
  | AgentStatusEvent
  | ToolCallEvent
  | ToolResultEvent
  | EdgeActiveEvent
  | TaskCreatedEvent
  | TaskUpdateEvent
  | CoreStateEvent
  | LogEvent
  | SnapshotEvent;

// ── Node config (mirrors nodes.config.json) ──
export interface NodeDef {
  id: string;
  label: string;
  ring: "inner" | "outer";
  type: "agent" | "tool";
  angle: number;
  role?: string;
  mcp?: string;
  connects?: string[];
}
export interface NodesConfig {
  version: number;
  core: { id: string; label: string; type: string };
  nodes: NodeDef[];
}
