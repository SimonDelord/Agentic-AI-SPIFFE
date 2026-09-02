# OpenShift AI and CPU LLM

Install Red Hat OpenShift AI on this cluster, then serve a small chat model
with KServe RawDeployment and the vLLM **CPU** runtime.

This cluster starts as CPU-only workers (`m5.4xlarge`). Add a GPU worker from `gpu/` (`g4dn.xlarge`, 1× Tesla T4) when you want a stronger model than CPU TinyLlama.

## What this folder deploys

| Step | What |
|------|------|
| `operator/` | cert-manager (KServe prerequisite) + OpenShift AI Operator `stable-3.x` + `DataScienceCluster` |
| `llm/` | TinyLlama on CPU, then Llama 3.2 3B Instruct on the T4 (`deploy-gpu.sh`) |
| `gpu/` | Single `g4dn.xlarge` MachineSet + NFD + NVIDIA GPU Operator |

Enabled OpenShift AI components: **dashboard**, **KServe** (RawDeployment), **MLflow**.

## Prerequisites

- `oc` logged in as a cluster admin
- Default StorageClass (`gp3-csi` on this cluster)
- Pull access to `registry.redhat.io` (cluster pull secret)

## Install

```bash
# 1. cert-manager + OpenShift AI Operator + DataScienceCluster
./openshift-ai/operator/deploy.sh

# 2. CPU LLM (optional fallback)
./openshift-ai/llm/deploy.sh

# 3. GPU LLM on the T4 (after gpu/ is Ready)
./openshift-ai/llm/deploy-gpu.sh
./openshift-ai/llm/verify-gpu.sh
```

In-cluster URL for the agents (GPU Llama 3.2 3B, once Loaded):

```text
MODEL_URL  = http://llama-3-2-3b-instruct-predictor.agentic-llm.svc.cluster.local/v1
MODEL_NAME = llama-3-2-3b-instruct
```

CPU TinyLlama remains as a fallback at `http://tinyllama-predictor.agentic-llm.svc.cluster.local/v1`.

## Notes

- KServe is **RawDeployment** so this demo does not need OpenShift Serverless or Service Mesh.
- TinyLlama is small and not a strong tool-caller. That is a CPU constraint, not the SPIFFE design. When a GPU is available, change `storageUri` / `MODEL_NAME` to a larger instruct model.
Dashboard after install:

```bash
oc get route -n redhat-ods-applications
```
