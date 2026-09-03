# PostgreSQL for incident triage

Deploys Postgres into **`agentic-db`**, a different namespace from the agents
(`agentic-ai`) and from the GPU LLM (`agentic-llm`).

Phase 1 uses password auth (`demo-incidents`). Each agent still
**stamps its SPIFFE ID** on writes (`agent_writes.spiffe_id`). Postgres does
not yet authorize by SPIFFE ID — that is [phase 2](../../phase-2/).

From the repo root:

```bash
./phase-1/postgres/deploy.sh
```

Seed data: incident **1042** (checkout p95 latency) plus a similar historical
incident **1011**. `incidents` is **read-only input**. Agents only INSERT into
`agent_writes` (triage fields, `agent_name`, `spiffe_id`).
