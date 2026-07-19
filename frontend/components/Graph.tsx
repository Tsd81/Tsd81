"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  type Edge,
  type Node,
  type NodeTypes,
} from "reactflow";
import "reactflow/dist/style.css";

import type { NodesConfig } from "@/lib/events";
import { placeNodes } from "@/lib/layout";
import type { OrchestratorState } from "@/lib/useOrchestrator";
import { CoreNode } from "./CoreNode";
import { OrbNode } from "./OrbNode";
import { FlowEdge } from "./FlowEdge";

const nodeTypes: NodeTypes = { core: CoreNode, orb: OrbNode };
const edgeTypes = { flow: FlowEdge };

interface GraphProps {
  cfg: NodesConfig;
  state: OrchestratorState;
  onNodeClick?: (id: string) => void;
}

export function Graph({ cfg, state, onNodeClick }: GraphProps) {
  const placed = useMemo(() => placeNodes(cfg), [cfg]);

  // Static edge skeleton: core→inner agents, tools→their connected agents.
  const edgePairs = useMemo(() => {
    const pairs: { from: string; to: string; ring: "core" | "tool" }[] = [];
    for (const n of cfg.nodes) {
      if (n.ring === "inner")
        pairs.push({ from: cfg.core.id, to: n.id, ring: "core" });
    }
    for (const n of cfg.nodes) {
      if (n.type === "tool" && n.connects) {
        for (const a of n.connects)
          pairs.push({ from: a, to: n.id, ring: "tool" });
      }
    }
    return pairs;
  }, [cfg]);

  const rfNodes: Node[] = useMemo(() => {
    const core: Node = {
      id: cfg.core.id,
      type: "core",
      position: { x: -56, y: -56 }, // center-ish; fitView recenters anyway
      data: { label: cfg.core.label, state: state.core },
      draggable: false,
      selectable: false,
    };
    const others: Node[] = placed.map((n) => ({
      id: n.id,
      type: "orb",
      position: { x: n.x, y: n.y },
      data: {
        label: n.label,
        ring: n.ring,
        type: n.type,
        state: state.nodes[n.id] ?? "idle",
      },
      draggable: false,
      selectable: false,
    }));
    return [core, ...others];
  }, [cfg, placed, state.core, state.nodes]);

  const rfEdges: Edge[] = useMemo(() => {
    return edgePairs.map(({ from, to, ring }) => {
      const active =
        state.activeEdges.has(`${from}->${to}`) ||
        state.activeEdges.has(`${to}->${from}`);
      return {
        id: `${from}-${to}`,
        source: from,
        target: to,
        type: "flow",
        data: { active, ring },
      };
    });
  }, [edgePairs, state.activeEdges]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={(_, n) => onNodeClick?.(n.id)}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.3}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag
      zoomOnScroll
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={28}
        size={1}
        color="rgba(255,255,255,0.05)"
      />
    </ReactFlow>
  );
}
