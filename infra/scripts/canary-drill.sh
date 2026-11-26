#!/usr/bin/env bash
set -euo pipefail
NS="${1:-taskflow-dev}"
if [[ "$NS" == "taskflow-prod" ]]; then
  echo "Refusing to inject failures into production." >&2
  exit 2
fi
cleanup() {
  kubectl patch configmap taskflow-config -n "$NS" --type merge \
    -p '{"data":{"APP_FAILURE_RATE":"0"}}' >/dev/null || true
  kubectl delete pod taskflow-load -n "$NS" --ignore-not-found >/dev/null || true
  kubectl patch rollout taskflow -n "$NS" --type merge \
    -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"taskflow.devops/recover\":\"$(date +%s)\"}}}}}" >/dev/null || true
}
trap cleanup EXIT
echo "==> Injecting a deterministic 100% 5xx failure rate into $NS"
kubectl patch configmap taskflow-config -n "$NS" --type merge \
  -p '{"data":{"APP_FAILURE_RATE":"1.0"}}'
kubectl patch rollout taskflow -n "$NS" --type merge \
  -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"taskflow.devops/drill\":\"$(date +%s)\"}}}}}"
echo "==> Generating traffic to the shared TaskFlow Service"
kubectl delete pod taskflow-load -n "$NS" --ignore-not-found
kubectl run taskflow-load -n "$NS" \
  --image=busybox:1.36.1 \
  --labels=delivery-check=true,app=taskflow-load \
  --restart=Never \
  --command -- sh -c 'i=0; while [ "$i" -lt 600 ]; do wget -q -O /dev/null http://taskflow/api/v1/tasks || true; sleep 1; i=$((i+1)); done'
kubectl wait --for=condition=Ready pod/taskflow-load -n "$NS" --timeout=90s
echo "==> Watching Argo Rollouts abort the canary from Prometheus analysis"
for _ in $(seq 1 60); do
  PHASE="$(kubectl get rollout taskflow -n "$NS" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  echo "rollout phase: ${PHASE:-unknown}"
  if [[ "$PHASE" == "Degraded" ]]; then
    echo "Canary analysis failed as expected; stable ReplicaSet remains serving."
    kubectl get analysisrun -n "$NS" || true
    exit 0
  fi
  sleep 5
done
echo "Rollout did not reach Degraded within five minutes; inspect AnalysisRun events." >&2
exit 1
