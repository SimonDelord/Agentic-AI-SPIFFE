#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if ! oc get crd inferenceservices.serving.kserve.io >/dev/null 2>&1; then
  echo "KServe CRDs are not present. Run ../operator/deploy.sh first and wait until the DataScienceCluster is Ready." >&2
  exit 1
fi

echo "==> data science project + vLLM CPU TinyLlama"
oc apply -f "${ROOT}/00-namespace.yaml"
oc apply -f "${ROOT}/01-anyuid-scc.yaml"
oc apply -f "${ROOT}/02-servingruntime-vllm-cpu.yaml"
oc apply -f "${ROOT}/03-inferenceservice.yaml"

echo "==> wait for InferenceService Ready (model pull + CPU load can take 10+ minutes)"
for i in $(seq 1 90); do
  ready=$(oc get inferenceservice tinyllama -n agentic-llm -o jsonpath='{.status.modelStatus.states.activeModelState}' 2>/dev/null || true)
  echo "  modelState=${ready:-none}"
  if [[ "${ready}" == "Loaded" ]]; then
    echo
    oc get inferenceservice tinyllama -n agentic-llm
    oc get svc -n agentic-llm
    echo
    echo "In-cluster MODEL_URL=http://tinyllama-predictor.agentic-llm.svc.cluster.local/v1"
    echo "MODEL_NAME=tinyllama"
    exit 0
  fi
  sleep 15
done

echo "InferenceService did not become Ready" >&2
oc get inferenceservice tinyllama -n agentic-llm -o yaml | sed -n '/status:/,$p' | head -80
oc get pods -n agentic-llm
oc describe inferenceservice tinyllama -n agentic-llm | tail -40
exit 1
