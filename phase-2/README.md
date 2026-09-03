# Phase 2 — Postgres authorizes by SPIFFE ID

**Status: not built.** This folder is the design for the next demo, not working code.

Phase 1 proves two identical agents can disagree, and that each write is stamped with a SPIFFE ID. Postgres still uses a shared password, so **both agents see the same rows**.

Phase 2 keeps that setup (same image, same internal MCP, same GPU model) and changes **what each identity is allowed to read**.

```
same code + different SPIFFE ID + different authorized rows
        → different answers
```

---

## What this phase should prove

1. **Authentication** — Postgres accepts the agent because of its SPIFFE ID, not because it knows `demo-incidents`.
2. **Authorization** — `agent-a` and `agent-b` are mapped to different grants / row-level security policies.
3. **Divergence for a new reason** — they disagree because they did not see the same incident world, not only because the LLM sampled differently.

A concrete story: **engineering vs finance**.

| Identity | Sees |
|----------|------|
| `…/sa/agent-a` (engineering) | Checkout / payments incidents, service ownership, similar outages |
| `…/sa/agent-b` (finance) | Billing / refund / cost rows for the same incident id, or a filtered subset |

Same prompt: `Triage incident 1042`. Different tool results. Different write-up. SPIFFE ID still stamped (and now also **enforced**) on the session.

MCP stays **in-process in the agent pod**, same as phase 1. The process talking to Postgres is still the agent, so RLS sees `agent-a` or `agent-b`. Do not introduce a remote MCP here — that is [phase 3](../phase-3/).

---

## JWT-SVID is enough

Do not spend this phase proving X.509 mTLS into Postgres. The pattern already exists in
[SPIFFE-PostgreSQL](https://github.com/SimonDelord/SPIFFE-PostgreSQL): present a **JWT-SVID** to PostgreSQL, map the SPIFFE ID to a database role, then apply grants / RLS.

What to reuse from that repo:

- SPIRE issues a JWT-SVID for the workload
- Postgres (or a small auth hook in front of it) verifies the JWT against the SPIRE JWKS
- `current_setting` / a session GUC holds the SPIFFE ID for RLS

What this repo already has from [phase 1](../phase-1/):

- SPIRE via Zero Trust Workload Identity Manager
- ClusterSPIFFEID for `agent-a` / `agent-b`
- `identity.py` fetching an X.509-SVID from the Workload API (extend this to JWT)
- `agent_writes.spiffe_id` as the audit column

---

## Suggested shape (when we build it)

Keep phase 1 agents. Add:

| Piece | Change |
|--------|--------|
| **Postgres** | Roles `engineering` / `finance` (or equivalent). RLS on `incidents` / `services` / maybe a `finance_*` table. |
| **Seed data** | Rows agent-a can see that agent-b cannot, and the reverse. |
| **Agent DB client** | Present JWT-SVID; drop the shared password for agent connections. |
| **SQL UI** | Still last-N writes, but also show *which rows each agent was allowed to read*. |
| **Demo script** | One repeat-run that prints: same prompt, different `SELECT` results, different triage. |

Out of scope for this phase:

- External / shared MCP (phase 3)
- Tool filtering by identity (phase 3; here the tool *list* stays the same, the *data* changes)
- X.509 mTLS as a requirement

---

## Trap to avoid

If both agents still `SELECT *` from the same tables with the same password, this is still phase 1 with extra YAML. The audience should be able to point at two Postgres policies and say: **that** is why the answers diverged.
