# MCP Connectors

This folder will hold one mock MCP server per outer/tool node
(Email, Calendar, Drive, Memory). They are stood up in **Phase 4** with a
real MCP interface returning realistic mock data, structured so swapping in
real connectors (Phase 5) is trivial.

Phase 0 ships only the skeleton — no MCP servers run yet. The outer tool
nodes in the dashboard are currently driven by the fake event loop so the
graph behaves end-to-end before the real protocol lands.
