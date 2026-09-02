# Incident-triage agents

Same image, two Jobs: `agent-a` and `agent-b` in namespace `agentic-ai`.

Both call the GPU Llama 3.2 3B Instruct endpoint in `agentic-llm` (port **8080**) and write
triage results to Postgres in `agentic-db`. Each run is an MLflow trace.

```bash
# Postgres first
./postgres/deploy.sh

# MLflow tracking server (OpenShift AI)
oc apply -f openshift-ai/mlflow/00-mlflow.yaml

# Build image and run both agents
chmod +x k8s/deploy.sh
./k8s/deploy.sh
```

Update `MLFLOW_TRACKING_URI` in `k8s/01-configmap.yaml` if the Service
hostname or port differs after the MLflow CR becomes Ready.
