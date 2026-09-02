#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

oc apply -f "${ROOT}/00-namespace.yaml"
oc apply -f "${ROOT}/01-secret.yaml"
oc apply -f "${ROOT}/02-pvc.yaml"
oc apply -f "${ROOT}/03-init-configmap.yaml"
oc apply -f "${ROOT}/04-deployment.yaml"

echo "Waiting for Postgres"
oc rollout status deployment/postgres -n agentic-db --timeout=5m

oc delete job postgres-seed -n agentic-db --ignore-not-found
oc apply -f "${ROOT}/05-seed-job.yaml"
oc wait --for=condition=complete job/postgres-seed -n agentic-db --timeout=3m

echo "Seed complete. Sample rows:"
oc exec -n agentic-db deploy/postgres -- \
  env PGPASSWORD=demo-incidents \
  psql -U app -d incidents -c "SELECT id, title, severity, agent_name FROM incidents ORDER BY id;"
