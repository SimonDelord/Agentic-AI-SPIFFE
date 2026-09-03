#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS=agentic-ai
ITERATIONS="${1:-5}"

wait_job() {
  local name="$1"
  local timeout_s="${2:-600}"
  local t=0
  while (( t < timeout_s )); do
    local succeeded failed
    succeeded="$(oc get job "${name}" -n "${NS}" -o jsonpath='{.status.succeeded}' 2>/dev/null || true)"
    failed="$(oc get job "${name}" -n "${NS}" -o jsonpath='{.status.failed}' 2>/dev/null || true)"
    if [[ "${succeeded}" == "1" ]]; then
      echo "  ${name} Complete"
      return 0
    fi
    if [[ -n "${failed}" && "${failed}" != "0" ]]; then
      echo "  ${name} Failed"
      oc logs -n "${NS}" "job/${name}" --tail=40 || true
      return 1
    fi
    sleep 5
    t=$((t + 5))
  done
  echo "  ${name} timed out after ${timeout_s}s"
  return 1
}

reset_incident() {
  echo "  Resetting incidents 1042 triage fields"
  oc exec -n agentic-db deploy/postgres -c postgres -- \
    env PGPASSWORD=demo-incidents \
    psql -U app -d incidents -v ON_ERROR_STOP=1 -c \
    "UPDATE incidents SET severity = NULL, owner = NULL, root_cause = NULL, summary = NULL, agent_name = NULL, spiffe_id = NULL, updated_at = now() WHERE id = 1042;"
}

echo "Repeating incident-triage Jobs ${ITERATIONS} time(s); incidents table is read-only"
reset_incident
for i in $(seq 1 "${ITERATIONS}"); do
  echo
  echo "======== iteration ${i}/${ITERATIONS} ========"
  oc delete job agent-a agent-b -n "${NS}" --ignore-not-found --wait=true --timeout=120s || true
  oc apply -f "${ROOT}/k8s/04-agent-a-job.yaml"
  oc apply -f "${ROOT}/k8s/05-agent-b-job.yaml"
  wait_job agent-a
  wait_job agent-b
  echo "agent-a:"
  oc logs -n "${NS}" job/agent-a --tail=80 | grep -E 'spiffe_id=|FINAL |mlflow_run_id=' || true
  echo "agent-b:"
  oc logs -n "${NS}" job/agent-b --tail=80 | grep -E 'spiffe_id=|FINAL |mlflow_run_id=' || true
done

echo
echo "Done. Refresh the SQL UI:"
echo "  https://$(oc get route sql-ui -n agentic-ai -o jsonpath='{.spec.host}')"
