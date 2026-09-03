#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> vLLM CUDA + Llama 3.2 3B Instruct on the T4"
oc apply -f "${ROOT}/04-servingruntime-vllm-cuda.yaml"
oc apply -f "${ROOT}/05-inferenceservice-gpu.yaml"

echo "==> wait for GPU InferenceService Loaded (CUDA image + modelcar can take 10+ minutes)"
for i in $(seq 1 90); do
  state=$(oc get inferenceservice llama-3-2-3b-instruct -n agentic-llm -o jsonpath='{.status.modelStatus.states.activeModelState}' 2>/dev/null || true)
  echo "  modelState=${state:-none}"
  if [[ "${state}" == "Loaded" ]]; then
    oc get inferenceservice llama-3-2-3b-instruct -n agentic-llm
    oc get pods -n agentic-llm -o wide
    echo
    echo "MODEL_URL=http://llama-3-2-3b-instruct-predictor.agentic-llm.svc.cluster.local/v1"
    echo "MODEL_NAME=llama-3-2-3b-instruct"
    exit 0
  fi
  sleep 15
done

echo "GPU InferenceService did not become Loaded" >&2
oc get inferenceservice llama-3-2-3b-instruct -n agentic-llm -o yaml | sed -n '/status:/,$p' | head -80
oc get pods -n agentic-llm -o wide
oc describe inferenceservice llama-3-2-3b-instruct -n agentic-llm | tail -40
exit 1
