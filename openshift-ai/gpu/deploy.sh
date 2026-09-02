#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> GPU MachineSet (g4dn.xlarge x1, us-east-1a)"
oc apply -f "${ROOT}/00-machineset-g4dn.yaml"

echo "==> Node Feature Discovery Operator"
oc apply -f "${ROOT}/01-nfd-operator.yaml"

echo "==> wait for NFD CSV"
for i in $(seq 1 60); do
  phase=$(oc get csv -n openshift-nfd -o jsonpath='{.items[0].status.phase}' 2>/dev/null || true)
  echo "  nfd csv phase=${phase:-none}"
  [[ "${phase}" == "Succeeded" ]] && break
  sleep 10
done

echo "==> NodeFeatureDiscovery instance"
oc apply -f "${ROOT}/02-nfd-instance.yaml"

echo "==> NVIDIA GPU Operator"
oc apply -f "${ROOT}/03-gpu-operator.yaml"

echo "==> wait for GPU Operator CSV"
for i in $(seq 1 60); do
  phase=$(oc get csv -n nvidia-gpu-operator -o jsonpath='{.items[0].status.phase}' 2>/dev/null || true)
  echo "  gpu-operator csv phase=${phase:-none}"
  [[ "${phase}" == "Succeeded" ]] && break
  sleep 10
done

echo "==> ClusterPolicy"
oc apply -f "${ROOT}/04-clusterpolicy.yaml"

echo "==> MachineSet / Machine status"
oc get machineset agentic-ai-demo-tlrpb-gpu-us-east-1a -n openshift-machine-api
oc get machines -n openshift-machine-api -l machine.openshift.io/cluster-api-machineset=agentic-ai-demo-tlrpb-gpu-us-east-1a
echo
echo "When the node is Ready, check: oc describe node -l cluster-api/accelerator=nvidia-tesla-t4 | rg -i 'nvidia.com/gpu|Allocatable'"
