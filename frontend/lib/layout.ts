// Deterministic radial layout: compute x/y for each node from its ring + angle.
// Both rings orbit the central core so the graph is stable across reloads.

import type { NodeDef, NodesConfig } from "./events";

export const CENTER = { x: 0, y: 0 };
export const INNER_RADIUS = 280;
export const OUTER_RADIUS = 520;

export interface PlacedNode extends NodeDef {
  x: number;
  y: number;
}

export function placeNodes(cfg: NodesConfig): PlacedNode[] {
  return cfg.nodes.map((n) => {
    const r = n.ring === "inner" ? INNER_RADIUS : OUTER_RADIUS;
    const rad = (n.angle * Math.PI) / 180;
    return {
      ...n,
      x: CENTER.x + r * Math.cos(rad),
      y: CENTER.y + r * Math.sin(rad),
    };
  });
}
