"use client";

import { useState } from "react";
import { BACKEND_HTTP } from "@/lib/config";

export function TaskBar({ busy }: { busy: boolean }) {
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    const t = text.trim();
    if (!t || pending || busy) return;
    setPending(true);
    setErr(null);
    try {
      const r = await fetch(`${BACKEND_HTTP}/api/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setText("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setPending(false);
    }
  };

  const disabled = pending || busy;

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-[min(720px,90vw)]">
      <div className="flex items-center gap-2 rounded-full border border-white/15 bg-black/50 backdrop-blur px-3 py-2 shadow-lg">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={
            busy ? "Orchestrating… please wait" : "Ask the orchestrator to do something…"
          }
          disabled={disabled}
          className="flex-1 bg-transparent outline-none text-sm text-white placeholder:text-white/35 px-2 disabled:opacity-60"
        />
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="rounded-full px-4 py-1.5 text-sm font-medium bg-accent text-black disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 transition"
        >
          {disabled ? "…" : "Run"}
        </button>
      </div>
      {err && <div className="mt-1 text-center text-xs text-red-400">{err}</div>}
    </div>
  );
}
