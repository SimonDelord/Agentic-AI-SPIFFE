# SPIFFE/SPIRE for the agents

Installs Red Hat **Zero Trust Workload Identity Manager** (SPIRE server,
SPIRE agent DaemonSet, SPIFFE CSI driver) and a `ClusterSPIFFEID` that
issues identities to the incident-triage Jobs.

Postgres still uses the demo password. Phase 1 only **stamps** each
agent's SPIFFE ID on the row it writes (`agent_writes.spiffe_id`).
Authorization by SPIFFE ID is [phase 2](../../phase-2/).

Expected IDs:

```text
spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-a
spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-b
```

From the repo root:

```bash
./phase-1/spire/deploy.sh
./phase-1/postgres/deploy.sh
./phase-1/k8s/deploy.sh
```
