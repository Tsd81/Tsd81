"use client";

import { useEffect, useState } from "react";
import { BACKEND_HTTP } from "@/lib/config";

interface Weather {
  tempC: number;
  label: string;
  emoji: string;
  city: string;
}
interface HudData {
  greeting: string;
  history: string;
  city: string;
  weather: Weather | null;
}

export function Hud({ connected }: { connected: boolean }) {
  const [now, setNow] = useState<Date | null>(null);
  const [hud, setHud] = useState<HudData | null>(null);

  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const load = () =>
      fetch(`${BACKEND_HTTP}/api/hud`)
        .then((r) => r.json())
        .then(setHud)
        .catch(() => setHud(null));
    load();
    // Refresh HUD (weather) every 10 minutes.
    const t = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="absolute top-6 left-6 z-10 text-white/80 space-y-1 pointer-events-none">
      <div className="text-4xl font-light tabular-nums tracking-tight">
        {now ? now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--:--"}
      </div>
      <div className="text-sm text-white/60">
        {now ? now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" }) : ""}
      </div>
      {hud && (
        <>
          <div className="text-base text-white/85 pt-1">
            {hud.greeting}.
          </div>
          <div className="text-sm text-white/70">
            {hud.weather ? (
              <span>
                {hud.weather.emoji} {hud.weather.tempC}°C · {hud.weather.label} ·{" "}
                {hud.weather.city}
              </span>
            ) : (
              <span className="text-white/35">
                Weather · {hud.city} — unavailable
              </span>
            )}
          </div>
          <div className="text-xs text-white/45 max-w-xs pt-1">{hud.history}</div>
        </>
      )}
      <div className="flex items-center gap-2 pt-2 text-[11px]">
        <span
          className={[
            "h-2 w-2 rounded-full",
            connected ? "bg-emerald-400" : "bg-red-500",
          ].join(" ")}
        />
        <span className="text-white/45">
          {connected ? "live" : "reconnecting…"}
        </span>
      </div>
    </div>
  );
}
