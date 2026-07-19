"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { motion, useReducedMotion } from "framer-motion";
import type { AgentState } from "@/lib/events";

export interface OrbData {
  label: string;
  ring: "inner" | "outer";
  type: "agent" | "tool";
  state: AgentState;
}

const STATE_STYLE: Record<
  AgentState,
  { ring: string; glow: string; dim: number }
> = {
  idle: { ring: "border-white/15", glow: "", dim: 0.55 },
  thinking: { ring: "border-accent/60", glow: "shadow-glow", dim: 0.9 },
  working: { ring: "border-accent", glow: "shadow-glow", dim: 1 },
  done: { ring: "border-emerald-400/70", glow: "", dim: 0.85 },
  error: { ring: "border-red-500", glow: "", dim: 1 },
};

function OrbNodeImpl({ data }: NodeProps<OrbData>) {
  const s = STATE_STYLE[data.state] ?? STATE_STYLE.idle;
  const active = data.state === "working" || data.state === "thinking";
  const isError = data.state === "error";
  const isTool = data.type === "tool";
  const reduce = useReducedMotion();
  const animate = !reduce;

  return (
    <div className="relative flex flex-col items-center select-none">
      <Handle type="target" position={Position.Top} className="!opacity-0" />

      {/* Glow halo behind active / error nodes */}
      {(active || isError) && (
        <motion.div
          aria-hidden
          className="absolute rounded-full"
          style={{
            top: isTool ? -6 : -8,
            height: isTool ? 60 : 80,
            width: isTool ? 60 : 80,
            background: isError
              ? "radial-gradient(circle, rgba(239,68,68,0.35) 0%, rgba(239,68,68,0) 70%)"
              : "radial-gradient(circle, rgba(45,212,191,0.30) 0%, rgba(45,212,191,0) 70%)",
          }}
          animate={animate ? { opacity: [0.4, 0.8, 0.4] } : { opacity: 0.6 }}
          transition={{ duration: 1.6, repeat: animate ? Infinity : 0, ease: "easeInOut" }}
        />
      )}

      <motion.div
        animate={
          active && animate
            ? { scale: [1, 1.08, 1] }
            : isError && animate
            ? { scale: [1, 1.04, 1] }
            : { scale: 1 }
        }
        transition={
          active && animate
            ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" }
            : { duration: 0.4 }
        }
        style={{ opacity: s.dim }}
        className={[
          "rounded-full border backdrop-blur-sm flex items-center justify-center",
          isTool ? "h-12 w-12" : "h-16 w-16",
          isTool ? "bg-nodedim" : "bg-node",
          s.ring,
          s.glow,
        ].join(" ")}
      >
        <span
          className={[
            "rounded-full",
            isTool ? "h-2.5 w-2.5" : "h-3.5 w-3.5",
            data.state === "error"
              ? "bg-red-500"
              : active
              ? "bg-accent"
              : data.state === "done"
              ? "bg-emerald-400"
              : "bg-white/30",
          ].join(" ")}
        />
      </motion.div>
      <div
        className={[
          "mt-2 text-[11px] tracking-wide whitespace-nowrap transition-opacity",
          active ? "text-white opacity-100" : "text-white/55 opacity-80",
          isTool ? "uppercase" : "",
        ].join(" ")}
      >
        {data.label}
      </div>
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
}

export const OrbNode = memo(OrbNodeImpl);
