#!/usr/bin/env bash
set -euo pipefail
NS="${1:-taskflow-dev}"
echo "==> Cluster and platform resources"
kubectl get nodes -o wide
kubectl get namespace "$NS"
kubectl get rollout,service,ingress,hpa,pdb,servicemonitor,prometheusrule,networkpolicy -n "$NS"
kubectl get analysisrun,analysistemplate -n "$NS" || true
echo "==> Workload readiness"
kubectl wait --for=condition=Ready pod -l app=taskflow -n "$NS" --timeout=300s
kubectl get rollout taskflow -n "$NS" -o jsonpath='{.status.phase}{"\n"}'
echo "==> Application smoke test from inside the service network"
kubectl delete pod taskflow-smoke -n "$NS" --ignore-not-found
kubectl run taskflow-smoke -n "$NS" \
  --image=curlimages/curl:8.10.1 \
  --labels=delivery-check=true \
  --restart=Never \
  --command -- sh -c 'set -e; curl -fsS http://taskflow/healthz; echo; curl -fsS http://taskflow/readyz; echo; curl -fsS http://taskflow/api/v1/tasks; echo; curl -fsS http://taskflow/metrics | grep taskflow_build_info'
kubectl wait --for=condition=Succeeded pod/taskflow-smoke -n "$NS" --timeout=180s || {
  kubectl logs taskflow-smoke -n "$NS" || true
  exit 1
}
kubectl logs taskflow-smoke -n "$NS"
kubectl delete pod taskflow-smoke -n "$NS" --ignore-not-found
echo "Platform verification passed for $NS."
