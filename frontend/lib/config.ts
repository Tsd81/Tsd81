// Runtime config. NEXT_PUBLIC_* vars are inlined at build time but we also
// fall back to sensible localhost defaults for `npm run dev`.

export const BACKEND_HTTP =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export const BACKEND_WS =
  process.env.NEXT_PUBLIC_WS_URL ??
  BACKEND_HTTP.replace(/^http/, "ws") + "/ws";
