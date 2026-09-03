#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
NS=zero-trust-workload-identity-manager

oc apply -f "${ROOT}/00-namespace.yaml"
oc apply -f "${ROOT}/01-operatorgroup.yaml"
oc apply -f "${ROOT}/02-subscription.yaml"

echo "Waiting for Zero Trust Workload Identity Manager CSV"
for i in $(seq 1 60); do
  phase="$(oc get csv -n "${NS}" -o jsonpath='{range .items[*]}{.spec.displayName}{"|"}{.status.phase}{"\n"}{end}' 2>/dev/null | grep -i 'zero trust' | awk -F'|' '{print $2}' | tail -1 || true)"
  echo "  CSV phase=${phase:-unknown}"
  if [[ "${phase}" == "Succeeded" ]]; then
    break
  fi
  sleep 10
done

oc apply -f "${ROOT}/03-zerotrustworkloadidentitymanager.yaml"
oc apply -f "${ROOT}/04-spireserver.yaml"
oc apply -f "${ROOT}/05-spireagent.yaml"
oc apply -f "${ROOT}/06-spiffecsidriver.yaml"

echo "Waiting for SPIRE server/agent/CSI pods"
for i in $(seq 1 60); do
  oc get pods -n "${NS}"
  ready_server="$(oc get pods -n "${NS}" -l app.kubernetes.io/name=server --no-headers 2>/dev/null | awk '$2 ~ /\// && $3=="Running"' | wc -l | tr -d ' ')"
  ready_agent="$(oc get ds -n "${NS}" 2>/dev/null | grep -i spire-agent | awk '{print $4}' | tail -1)"
  if oc get pods -n "${NS}" --no-headers 2>/dev/null | grep -qiE 'spire-server|spire-controller' && \
     oc get ds -n "${NS}" --no-headers 2>/dev/null | grep -qi spire-agent; then
    server_ok="$(oc get pods -n "${NS}" --no-headers 2>/dev/null | awk '/spire-server/ && $3=="Running" && $2 ~ /^[1-9]/ {c++} END {print c+0}')"
    agent_ok="$(oc get ds -n "${NS}" --no-headers 2>/dev/null | awk '/agent/ {print $4}' | head -1)"
    csi_ok="$(oc get ds -n "${NS}" --no-headers 2>/dev/null | awk '/csi|spiffe/ {print $4}' | head -1)"
    echo "  server_running=${server_ok} agent_ready=${agent_ok} csi_ready=${csi_ok}"
    if [[ "${server_ok}" -ge 1 && "${agent_ok}" != "0" && -n "${agent_ok}" ]]; then
      break
    fi
  fi
  sleep 10
done

oc apply -f "${ROOT}/07-clusterspiffeid.yaml"
oc get clusterspiffeid agentic-ai-agents
oc get pods -n "${NS}"
