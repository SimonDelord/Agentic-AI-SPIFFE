#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-agentic-llm}"
SVC="${SVC:-llama-3-2-3b-instruct-predictor}"
MODEL="${MODEL:-llama-3-2-3b-instruct}"

echo "==> pods"
oc get pods -n "${NS}" -o wide

echo "==> InferenceService"
oc get inferenceservice -n "${NS}"

echo "==> GPU chat completion (in-cluster)"
oc delete pod llm-gpu-smoke -n "${NS}" --ignore-not-found
oc run llm-gpu-smoke --rm -i --restart=Never -n "${NS}" \
  --image=curlimages/curl:8.5.0 -- \
  curl -sS -m 120 -X POST "http://${SVC}.${NS}.svc.cluster.local:8080/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one short sentence.\"}],\"max_tokens\":48}"
echo
