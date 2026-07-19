"use client";

import { memo } from "react";
import { getBezierPath, type EdgeProps } from "reactflow";
import { useReducedMotion } from "framer-motion";

export interface FlowEdgeData {
  active: boolean;
  /** inner (core→agent) edges carry more particles than outer tool edges */
  ring: "core" | "tool";
}

const PARTICLE_TEAL = "#2dd4bf";

function FlowEdgeImpl({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps<FlowEdgeData>) {
  const reduce = useReducedMotion();
  const active = !!data?.active;

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const nParticles = data?.ring === "core" ? 3 : 2;
  const dur = 1.4; // seconds per traverse (core → node)

  return (
    <g>
      {/* Base path — always present, brightens when active. */}
      <path
        id={id}
        d={edgePath}
        fill="none"
        className="react-flow__edge-path"
        style={{
          stroke: active ? "rgba(45,212,191,0.55)" : "rgba(255,255,255,0.07)",
          strokeWidth: active ? 1.8 : 1,
        }}
      />

      {/* Flowing particles — only when active, and only if motion is allowed. */}
      {active &&
        !reduce &&
        Array.from({ length: nParticles }).map((_, i) => (
          <circle key={i} r={2.6} fill={PARTICLE_TEAL} opacity={0.9}>
            <animateMotion
              dur={`${dur}s`}
              begin={`-${(dur / nParticles) * i}s`}
              repeatCount="indefinite"
              keyPoints="0;1"
              keyTimes="0;1"
              calcMode="linear"
            >
              <mpath href={`#${id}`} />
            </animateMotion>
            <animate
              attributeName="opacity"
              values="0;1;1;0"
              keyTimes="0;0.15;0.85;1"
              dur={`${dur}s`}
              begin={`-${(dur / nParticles) * i}s`}
              repeatCount="indefinite"
            />
          </circle>
        ))}

      {/* Reduced-motion fallback: a single static bright dot near the target. */}
      {active && reduce && (
        <circle r={2.6} fill={PARTICLE_TEAL} opacity={0.9}>
          <animateMotion dur="0.01s" fill="freeze" keyPoints="0.8;0.8" keyTimes="0;1">
            <mpath href={`#${id}`} />
          </animateMotion>
        </circle>
      )}
    </g>
  );
}

export const FlowEdge = memo(FlowEdgeImpl);
