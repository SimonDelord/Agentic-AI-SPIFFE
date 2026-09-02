# OpenShift AI and CPU LLM

Install Red Hat OpenShift AI on this cluster, then serve a small chat model
with KServe RawDeployment and the vLLM **CPU** runtime.

This cluster has **no GPUs** (workers are `m5.4xlarge`). The model is
TinyLlama 1.1B from an OCI modelcar, which is enough to give agents an
OpenAI-compatible `/v1/chat/completions` endpoint. Swap the model later if
you add GPU nodes.

## What this folder deploys

| Step | What |
|------|------|
| `operator/` | cert-manager (KServe prerequisite) + OpenShift AI Operator `stable-3.x` + `DataScienceCluster` |
| `llm/` | Data science project, vLLM CPU `ServingRuntime`, TinyLlama `InferenceService` |

Enabled OpenShift AI components: **dashboard**, **KServe** (RawDeployment), **MLflow**.

## Prerequisites

- `oc` logged in as a cluster admin
- Default StorageClass (`gp3-csi` on this cluster)
- Pull access to `registry.redhat.io` (cluster pull secret)

## Install

```bash
# 1. cert-manager + OpenShift AI Operator + DataScienceCluster
./openshift-ai/operator/deploy.sh

# 2. CPU LLM (after the DSC is Ready)
./openshift-ai/llm/deploy.sh

# 3. Smoke-test the OpenAI-compatible API
./openshift-ai/llm/verify.sh
```

In-cluster URL for the agents (once the predictor is Ready):

```text
MODEL_URL  = http://tinyllama-predictor.agentic-llm.svc.cluster.local/v1
MODEL_NAME = tinyllama
```

## Notes

- KServe is **RawDeployment** so this demo does not need OpenShift Serverless or Service Mesh.
- TinyLlama is small and not a strong tool-caller. That is a CPU constraint, not the SPIFFE design. When a GPU is available, change `storageUri` / `MODEL_NAME` to a larger instruct model.
Dashboard after install:

```bash
oc get route -n redhat-ods-applications
```
