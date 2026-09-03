# Phase 1 — same input, two outputs

**Status: built.** This is the working demo.

Two identical agents triage the same incident. The only intended difference is SPIFFE identity. Each pod runs its own MCP toolbox **in-process**. Postgres still uses a demo password; each write is **stamped** with the pod’s SPIFFE ID.

What this phase is *not*: Postgres does not yet authorize by SPIFFE ID (that is [phase 2](../phase-2/)). MCP is not a shared remote service (that is [phase 3](../phase-3/)).

---

## What you should see

- Same image, same GPU model, same prompt (`Triage incident 1042`), same tools.
- Different ServiceAccounts → different SPIFFE IDs.
- Different triage answers (severity, owner, root cause) across agents and across repeats.
- `incidents` stays the **read-only alert**. Every conclusion is an `INSERT` into `agent_writes` with `agent_name` + `spiffe_id`.
- MLflow traces tagged with `agent`, `spiffe_id`, `incident_id`.

Expected IDs on this cluster:

```text
spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-a
spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-b
```

Llama 3.2 3B on this runtime accepts **one tool call per turn**. The agent loop enforces that.

---

## Layout

| Path | What |
|------|------|
| [`openshift-ai/`](openshift-ai/) | cert-manager, OpenShift AI operator, GPU Llama 3.2 3B, MLflow |
| [`spire/`](spire/) | Zero Trust Workload Identity Manager + `ClusterSPIFFEID` for the agent Jobs |
| [`postgres/`](postgres/) | PostgreSQL 16 in `agentic-db` (password `demo-incidents`) |
| [`agent/`](agent/) | Agent loop + in-process MCP tools + `identity.py` (Workload API) |
| [`k8s/`](k8s/) | Namespace `agentic-ai`: two Jobs, two ServiceAccounts, CSI socket |
| [`sql-ui/`](sql-ui/) | Last 10 `agent_writes`, agent-a left / agent-b right |

| Piece | Namespace | Notes |
|--------|-----------|--------|
| GPU Llama 3.2 3B Instruct | `agentic-llm` | vLLM CUDA on the T4; clients must use **port 8080** |
| MLflow | `redhat-ods-applications` | UI: https://rh-ai.apps.agentic-ai-demo.sandbox1133.opentlc.com/mlflow |
| Agents `agent-a`, `agent-b` | `agentic-ai` | Same image, CSI `unix:///spiffe-workload-api/spire-agent.sock` |
| PostgreSQL | `agentic-db` | Password auth; SPIFFE ID columns on writes |
| SPIRE | `zero-trust-workload-identity-manager` | CSI driver `csi.spiffe.io` |
| SQL write viewer | `agentic-ai` | https://sql-ui-agentic-ai.apps.agentic-ai-demo.sandbox1133.opentlc.com |

In-cluster model URL:

```text
MODEL_URL  = http://llama-3-2-3b-instruct-predictor.agentic-llm.svc.cluster.local:8080/v1
MODEL_NAME = llama-3-2-3b-instruct
```

The predictor Service is headless (`ClusterIP: None`) and maps port 80 to targetPort 8080. Connecting to port 80 is refused.

---

## MCP: colocated on purpose

| Piece | What | Role |
|--------|------|------|
| **MCP client** | `agent/app.py` | Talks to OpenShift AI, calls tools |
| **MCP server** | `agent/mcp_server.py` | `get_incident`, `get_service`, `list_similar_incidents`, `update_incident` |

Colocate them in the same pod. The process that opens Postgres is still the agent workload, so the SPIFFE ID on the write is `agent-a` or `agent-b`.

Do **not** put a shared remote MCP in front of Postgres in this phase. Postgres would only see the MCP server’s identity. That problem is exactly what [phase 3](../phase-3/) has to solve.

`update_incident` does **not** `UPDATE incidents`. Incident 1042 stays the original alert. Otherwise a second run copies the first agent’s answer and they look identical.

---

## Observability

SPIFFE tells you **who** wrote. MLflow tells you **what the agent did**.

```text
trace  (incident-1042, agent-a, spiffe://.../agent-a)
├── llm.chat
├── mcp.get_incident
├── mcp.get_service
├── mcp.list_similar_incidents
├── llm.chat
└── mcp.update_incident
```

| You need to see | Where it lives |
|-----------------|----------------|
| Why the model chose that severity, which tools ran | **MLflow traces** |
| Who wrote the row | **`agent_writes.spiffe_id`** |
| That SPIRE issued this SVID | **SPIRE / workload attestation** |

Correlate with `incident_id` + `spiffe_id`. MLflow will not show the handshake. Postgres will not show the prompt.

---

## Deploy (from the repo root)

```bash
./phase-1/openshift-ai/operator/deploy.sh
./phase-1/openshift-ai/gpu/deploy.sh
./phase-1/openshift-ai/llm/deploy-gpu.sh
oc apply -f phase-1/openshift-ai/mlflow/00-mlflow.yaml

./phase-1/spire/deploy.sh
./phase-1/postgres/deploy.sh
./phase-1/k8s/deploy.sh
./phase-1/sql-ui/deploy.sh
```

Repeat the same 1042 prompt without rebuilding the image:

```bash
./phase-1/k8s/repeat-run.sh 5
```

Then refresh the SQL UI. You should see within-pair and across-iteration divergence, with incident 1042 still blank.

---

## Sample SPIFFE-stamped run

Workspace `agentic-ai`, experiment `incident-triage`:

| Agent | SPIFFE ID | MLflow run |
|--------|-----------|------------|
| agent-a | `spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-a` | `9d3e7d933dca4bc79e1ce0bd6f68d557` |
| agent-b | `spiffe://apps.agentic-ai-demo.sandbox1133.opentlc.com/ns/agentic-ai/sa/agent-b` | `2fc2d137f5b140f98ff38581673ba88c` |

- https://rh-ai.apps.agentic-ai-demo.sandbox1133.opentlc.com/mlflow/#/experiments/1/runs/9d3e7d933dca4bc79e1ce0bd6f68d557?workspace=agentic-ai
- https://rh-ai.apps.agentic-ai-demo.sandbox1133.opentlc.com/mlflow/#/experiments/1/runs/2fc2d137f5b140f98ff38581673ba88c?workspace=agentic-ai

Later repeats append more `agent_writes` rows. Incident 1042 is not updated.
