#!/usr/bin/env bash
set -euo pipefail
NS="${1:-taskflow-dev}"
echo "==> Aborting active canary in $NS"
if kubectl argo rollouts abort taskflow -n "$NS"; then
  echo "Argo Rollouts plugin aborted the rollout."
else
  echo "Plugin unavailable; patching the Rollout status directly."
  kubectl patch rollout taskflow -n "$NS" --subresource=status --type merge \
    -p '{"status":{"abort":true}}'
fi
kubectl get rollout taskflow -n "$NS" -o wide
echo "To revert Git state to the last approved digest, restore the previous release.yaml and kustomization.yaml, then let Argo CD reconcile."
