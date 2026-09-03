# Phase 3 — external MCP that does not eat the identity

**Status: not built.** This folder is the design for the last demo, not working code.

Phases 1 and 2 colocate MCP **inside** the agent pod so Postgres sees the agent’s SPIFFE ID. That is honest, but it is not how teams actually ship MCP: a **shared MCP server** in front of tools and data.

Phase 3 moves MCP out of the pod. The risk is obvious: if the MCP server opens Postgres as *itself*, every write and every RLS check becomes `spiffe://…/mcp`. [Phase 2](../phase-2/) disappears.

```
Agent SVID  →  MCP authenticates + filters tools
            →  MCP passes that SVID/JWT through to Postgres
            →  RLS still sees agent-a or agent-b
```

---

## What this phase should prove

Two jobs, in order:

1. **Authenticate the caller and filter tools.**  
   The MCP server verifies the agent’s SVID. `agent-a` may get `get_incident` + `update_incident`. `agent-b` may get a different tool set (or the same tools with a smaller allow-list). The model can only call what MCP exposes **to that caller**.

2. **Passthrough to Postgres.**  
   When MCP runs a tool that hits SQL, it must present the **agent’s** JWT-SVID (or a token derived from it), not the MCP server’s own identity. Row-level security from phase 2 still applies to the agent.

Together: identity is used **twice** — once at the tool door, once at the data door — and the middle box does not replace the caller.

---

## Architecture

```
        ┌─────────────┐         ┌─────────────┐
        │  Agent A    │         │  Agent B    │
        │  MCP client │         │  MCP client │
        └──────┬──────┘         └──────┬──────┘
               │  SVID                 │  SVID
               └──────────┬────────────┘
                          ▼
                 ┌─────────────────┐
                 │  MCP server     │
                 │  1. verify SVID │
                 │  2. filter tools│
                 │  3. passthrough │
                 └────────┬────────┘
                          │  agent JWT / SVID
                          ▼
                     PostgreSQL
                   (RLS by agent)
```

Agents still call the same OpenShift AI GPU model. SPIRE still issues distinct IDs. Postgres policies from phase 2 stay.

---

## Trap to avoid

| Wrong | What the audience sees |
|--------|-------------------------|
| MCP uses its own DB user / SVID | Every row is `mcp`. Phase 2 RLS is gone. |
| MCP trusts a header `X-Agent-Name` | Anyone who can reach MCP can impersonate `agent-a`. |
| MCP verifies SVID then opens Postgres with the shared password | Authn at the edge, no authz at the data. |

The MCP process **will** have its own SPIFFE ID (it is a workload). That ID is for **agents → MCP** (who may call this server). It must **not** be the identity Postgres uses for RLS.

---

## Suggested shape (when we build it)

| Piece | Change |
|--------|--------|
| **MCP deployment** | New Service in `agentic-ai` (or `agentic-mcp`). Own ServiceAccount / SPIFFE ID. |
| **Agent** | MCP client talks to that Service (HTTP/SSE or similar), presenting its SVID. In-process `mcp_server.py` goes away. |
| **MCP authn** | Verify caller X.509 or JWT-SVID via the Workload API / SPIRE JWKS. |
| **Tool filter** | Config map: SPIFFE ID → allow-listed tool names. |
| **DB hop** | Forward the caller’s JWT-SVID to Postgres (same verification path as phase 2). |
| **SQL UI** | Show that writes still carry `agent-a` / `agent-b`, never the MCP server’s ID. |

Depends on [phase 1](../phase-1/) (agents, GPU, SPIRE) and [phase 2](../phase-2/) (Postgres authz by SPIFFE ID). Building phase 3 against password-auth Postgres would skip the punchline.

---

## Why this is the last rung

Phase 1: identity on the write.  
Phase 2: identity on the read.  
Phase 3: identity survives a shared tool server.

That is the story for agentic AI on OpenShift: SPIFFE is the stable handle when the model is not.
