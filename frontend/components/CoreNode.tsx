"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { motion, useReducedMotion } from "framer-motion";
import type { CoreState } from "@/lib/events";

export interface CoreData {
  label: string;
  state: CoreState;
}

function CoreNodeImpl({ data }: NodeProps<CoreData>) {
  const orchestrating = data.state === "orchestrating";
  const reduce = useReducedMotion();
  const pulse = orchestrating && !reduce;
  return (
    <div className="relative flex flex-col items-center select-none">
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <Handle type="target" position={Position.Top} className="!opacity-0" />

      {/* Soft breathing halo behind the ring */}
      <motion.div
        aria-hidden
        className="absolute top-0 h-28 w-28 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(255,138,61,0.35) 0%, rgba(255,138,61,0) 70%)",
        }}
        animate={pulse ? { scale: [1, 1.5, 1], opacity: [0.5, 0.85, 0.5] } : { scale: 1.2, opacity: 0.4 }}
        transition={{ duration: 2.4, repeat: pulse ? Infinity : 0, ease: "easeInOut" }}
      />

      {/* Outer orange ring */}
      <motion.div
        animate={
          pulse
            ? { scale: [1, 1.06, 1], opacity: [0.9, 1, 0.9] }
            : { scale: 1, opacity: 0.85 }
        }
        transition={{
          duration: pulse ? 1.6 : 0.6,
          repeat: pulse ? Infinity : 0,
          ease: "easeInOut",
        }}
        className="relative h-28 w-28 rounded-full border-2 border-core shadow-coreglow flex items-center justify-center bg-[#140d08]"
      >
        {/* Inner teal particle cluster */}
        <motion.div
          animate={reduce ? { rotate: 0 } : { rotate: 360 }}
          transition={{ duration: 8, repeat: reduce ? 0 : Infinity, ease: "linear" }}
          className="h-16 w-16 rounded-full flex items-center justify-center"
          style={{
            background:
              "radial-gradient(circle, rgba(45,212,191,0.35) 0%, rgba(45,212,191,0.05) 70%)",
          }}
        >
          <div className="h-3 w-3 rounded-full bg-accent shadow-glow" />
        </motion.div>
      </motion.div>

      <div className="mt-3 text-xs font-semibold tracking-[0.2em] text-core">
        {data.label.toUpperCase()}
      </div>
      <div
        className={[
          "mt-1 text-[10px] tracking-[0.25em] px-2 py-0.5 rounded-full border",
          orchestrating
            ? "text-accent border-accent/50 bg-accent/10"
            : "text-white/40 border-white/15",
        ].join(" ")}
      >
        {orchestrating ? "ORCHESTRATING" : "STANDBY"}
      </div>
    </div>
  );
}

export const CoreNode = memo(CoreNodeImpl);
