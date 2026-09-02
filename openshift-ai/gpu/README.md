# GPU worker (AWS)

One extra worker with a **small** NVIDIA GPU so we can replace CPU TinyLlama
with a GPU vLLM model later.

| Choice | Why |
|--------|-----|
| `g4dn.xlarge` | Smallest common AWS GPU for OpenShift: 1× Tesla T4 (16 GiB), 4 vCPU, 16 GiB RAM |
| Replicas `1` | Enough for a single InferenceService |
| AZ `us-east-1a` | Same region/AZ pattern as the existing workers |
| No taint | GPU Operator DaemonSets and the LLM pod can schedule without extra tolerations |

A GPU node does nothing for KServe until **Node Feature Discovery** and the **NVIDIA GPU Operator** expose `nvidia.com/gpu`. Those are included here.

## Apply

```bash
./openshift-ai/gpu/deploy.sh
```

Wait until:

```bash
oc get nodes -l nvidia.com/gpu.present=true
oc get machineset -n openshift-machine-api | grep gpu
```

A Ready node should show `nvidia.com/gpu: "1"` under Allocatable.
