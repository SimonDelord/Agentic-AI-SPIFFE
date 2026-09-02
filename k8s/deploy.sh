#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS=agentic-ai

oc apply -f "${ROOT}/k8s/00-namespace.yaml"
oc apply -f "${ROOT}/k8s/01-configmap.yaml"
oc apply -f "${ROOT}/k8s/02-db-secret.yaml"
oc apply -f "${ROOT}/k8s/03-build.yaml"
oc apply -f "${ROOT}/k8s/06-mlflow-rbac.yaml"

echo "Starting binary build from ${ROOT}/agent"
oc start-build incident-agent -n "${NS}" --from-dir="${ROOT}/agent" --follow --wait

echo "Deleting previous agent Jobs if they exist"
oc delete job agent-a agent-b -n "${NS}" --ignore-not-found
oc apply -f "${ROOT}/k8s/04-agent-a-job.yaml"
oc apply -f "${ROOT}/k8s/05-agent-b-job.yaml"

echo "Waiting for agent Jobs (LLM + tools; this can take a few minutes)"
oc wait --for=condition=complete job/agent-a -n "${NS}" --timeout=10m || true
oc wait --for=condition=complete job/agent-b -n "${NS}" --timeout=10m || true

echo "=== agent-a logs ==="
oc logs -n "${NS}" job/agent-a --tail=200 || true
echo "=== agent-b logs ==="
oc logs -n "${NS}" job/agent-b --tail=200 || true
