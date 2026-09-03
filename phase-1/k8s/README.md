# Incident-triage agents

Same image, two Jobs: `agent-a` and `agent-b` in namespace `agentic-ai`.

Both call the GPU Llama 3.2 3B Instruct endpoint in `agentic-llm` (port **8080**) and write
triage results to Postgres in `agentic-db`. Each run is an MLflow trace.

Each Job is one-shot. Repeat the same 1042 prompt N times (no image rebuild).
Agents read `incidents` and append to `agent_writes` (they do not update 1042).

From the repo root:

```bash
./phase-1/k8s/repeat-run.sh 5
```

```bash
# SPIRE (once)
./phase-1/spire/deploy.sh

# Postgres first
./phase-1/postgres/deploy.sh

# MLflow tracking server (OpenShift AI)
oc apply -f phase-1/openshift-ai/mlflow/00-mlflow.yaml

# Build image and run both agents
./phase-1/k8s/deploy.sh
```

Update `MLFLOW_TRACKING_URI` in `phase-1/k8s/01-configmap.yaml` if the Service
hostname or port differs after the MLflow CR becomes Ready.
