# PostgreSQL for incident triage

Deploys Postgres into **`agentic-db`**, a different namespace from the agents
(`agentic-ai`) and from the GPU LLM (`agentic-llm`).

This phase uses password auth (`demo-incidents`). SPIFFE/SPIRE mTLS is the
next step and is not configured here.

```bash
./postgres/deploy.sh
```

Seed data: incident **1042** (checkout p95 latency) plus a similar historical
incident **1011**. Agents write triage fields and an `agent_writes` audit row.
