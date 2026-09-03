# SPIFFE/SPIRE for the agents

Installs Red Hat **Zero Trust Workload Identity Manager** (SPIRE server,
SPIRE agent DaemonSet, SPIFFE CSI driver) and a `ClusterSPIFFEID` that
issues identities to the incident-triage Jobs.

Postgres still uses the demo password. This phase only **stamps** each
agent's SPIFFE ID on the row it writes (`incidents.spiffe_id` and
`agent_writes.spiffe_id`). mTLS into Postgres is not enabled yet.

Expected IDs:

```text
spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-a
spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-b
```

```bash
./spire/deploy.sh
./postgres/deploy.sh          # adds spiffe_id columns
./k8s/deploy.sh               # rebuilds agents with CSI socket + py-spiffe
```
