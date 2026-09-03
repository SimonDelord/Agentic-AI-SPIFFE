#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-agentic-llm}"
SVC="${SVC:-tinyllama-predictor}"

echo "==> pods"
oc get pods -n "${NS}"

echo "==> InferenceService"
oc get inferenceservice -n "${NS}"

echo "==> chat completion (in-cluster)"
oc run llm-smoke --rm -i --restart=Never -n "${NS}" \
  --image=registry.access.redhat.com/ubi9/ubi-minimal:latest \
  --command -- /bin/bash -c "
    microdnf -y install curl >/dev/null
    curl -sS -X POST http://${SVC}.${NS}.svc.cluster.local/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -d '{\"model\":\"tinyllama\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one sentence.\"}],\"max_tokens\":64}'
  "
echo
