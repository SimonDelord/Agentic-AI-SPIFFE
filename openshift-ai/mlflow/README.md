# MLflow on OpenShift AI

Cluster-scoped `MLflow` CR named `mlflow` (OpenShift AI 3.x operator). SQLite
backend plus a PVC for this demo.

```bash
oc apply -f openshift-ai/mlflow/00-mlflow.yaml
oc get mlflow mlflow -o yaml
oc get svc,route,pod -n redhat-ods-applications -l app.kubernetes.io/name=mlflow
```

In-cluster tracking URI (TLS on 8443):

```text
MLFLOW_TRACKING_URI=https://mlflow.redhat-ods-applications.svc:8443/mlflow
MLFLOW_TRACKING_AUTH=kubernetes-namespaced
MLFLOW_K8S_INTEGRATION=true
MLFLOW_WORKSPACE=agentic-ai
MLFLOW_TRACKING_INSECURE_TLS=true
```

Public UI: https://rh-ai.apps.agentic-ai-demo.sandbox1133.opentlc.com/mlflow

Agent ServiceAccounts need `edit` plus `mlflow-operator-mlflow-integration` in
`agentic-ai` (`k8s/06-mlflow-rbac.yaml`). The agent image installs
`mlflow[kubernetes]`. SPIFFE is not involved in this hop.
