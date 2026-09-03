# PostgreSQL for incident triage

Deploys Postgres into **`agentic-db`**, a different namespace from the agents
(`agentic-ai`) and from the GPU LLM (`agentic-llm`).

This phase uses password auth (`demo-incidents`). Each agent still
**stamps its SPIFFE ID** on writes (`spiffe_id` columns). Postgres mTLS
is not enabled yet.

```bash
./postgres/deploy.sh
```

Seed data: incident **1042** (checkout p95 latency) plus a similar historical
incident **1011**. Agents write triage fields, `agent_name`, `spiffe_id`, and
an `agent_writes` audit row.
