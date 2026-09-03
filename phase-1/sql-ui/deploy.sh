#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

oc apply -f "${ROOT}/k8s.yaml"
oc start-build sql-ui -n agentic-ai --from-dir="${ROOT}" --follow --wait
oc rollout restart deployment/sql-ui -n agentic-ai
oc rollout status deployment/sql-ui -n agentic-ai --timeout=3m
echo "UI: https://$(oc get route sql-ui -n agentic-ai -o jsonpath='{.spec.host}')"
