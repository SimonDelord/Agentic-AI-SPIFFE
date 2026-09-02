#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> cert-manager Operator"
oc apply -f "${ROOT}/00-cert-manager-namespace.yaml"
oc apply -f "${ROOT}/01-cert-manager-operatorgroup.yaml"
oc apply -f "${ROOT}/02-cert-manager-subscription.yaml"

echo "==> wait for cert-manager CSV"
oc wait csv -n cert-manager-operator --for=jsonpath='{.status.phase}'=Succeeded --timeout=600s \
  -l operators.coreos.com/openshift-cert-manager-operator.cert-manager-operator 2>/dev/null \
  || oc wait csv -n cert-manager-operator --all --for=jsonpath='{.status.phase}'=Succeeded --timeout=600s

echo "==> wait for cert-manager webhook"
oc wait -n cert-manager --for=condition=Available deploy --all --timeout=600s || true

echo "==> OpenShift AI Operator"
oc apply -f "${ROOT}/03-rhoai-namespace.yaml"
oc apply -f "${ROOT}/04-rhoai-operatorgroup.yaml"
oc apply -f "${ROOT}/05-rhoai-subscription.yaml"

echo "==> wait for rhods-operator CSV"
for i in $(seq 1 60); do
  csv=$(oc get csv -n redhat-ods-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  phase=$(oc get csv -n redhat-ods-operator -o jsonpath='{.items[0].status.phase}' 2>/dev/null || true)
  echo "  csv=${csv:-none} phase=${phase:-none}"
  if [[ "${phase}" == "Succeeded" ]]; then
    break
  fi
  sleep 10
done
phase=$(oc get csv -n redhat-ods-operator -o jsonpath='{.items[0].status.phase}' 2>/dev/null || true)
if [[ "${phase}" != "Succeeded" ]]; then
  echo "rhods-operator CSV did not become Succeeded" >&2
  oc get csv -n redhat-ods-operator
  exit 1
fi

echo "==> DataScienceCluster"
oc apply -f "${ROOT}/06-datasciencecluster.yaml"

echo "==> wait for DataScienceCluster Ready (this can take several minutes)"
for i in $(seq 1 90); do
  phase=$(oc get dsc default-dsc -o jsonpath='{.status.phase}' 2>/dev/null || true)
  echo "  dsc phase=${phase:-none}"
  if [[ "${phase}" == "Ready" ]]; then
    echo "OpenShift AI is Ready"
    oc get route -n redhat-ods-applications 2>/dev/null || true
    exit 0
  fi
  sleep 10
done

echo "DataScienceCluster did not become Ready" >&2
oc get dsc default-dsc -o yaml | sed -n '/status:/,$p' | head -80
exit 1
