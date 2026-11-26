#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/platform/versions.env"

for tool in docker kind kubectl helm openssl; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done

WITH_GITOPS="${WITH_GITOPS:-false}"
WITH_VELERO="${WITH_VELERO:-false}"
KIND_CLUSTER="${KIND_CLUSTER:-taskflow}"
DEV_NS="${DEV_NS:-taskflow-dev}"

echo "==> Creating reproducible Kind cluster ($KIND_CLUSTER)"
if ! kind get clusters | grep -qx "$KIND_CLUSTER"; then
  kind create cluster --name "$KIND_CLUSTER" --config "$ROOT/infra/kind-config.yaml" --image "kindest/node:v${KUBERNETES_VERSION}"
fi
kubectl cluster-info --context "kind-$KIND_CLUSTER"

echo "==> Registering pinned Helm chart repositories"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx --force-update
helm repo add jetstack https://charts.jetstack.io --force-update
helm repo add external-secrets https://charts.external-secrets.io --force-update
helm repo add argo https://argoproj.github.io/argo-helm --force-update
helm repo add grafana https://grafana.github.io/helm-charts --force-update
helm repo add kyverno https://kyverno.github.io/kyverno --force-update
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts --force-update
helm repo update

echo "==> Preparing monitoring namespace and generated Grafana admin secret"
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
GRAFANA_PASSWORD="$(openssl rand -hex 18)"
kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=admin-user=admin \
  --from-literal="admin-password=$GRAFANA_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Installing Prometheus Operator, Grafana and Alertmanager"
helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --version "$KUBE_PROMETHEUS_CHART" \
  --values "$ROOT/platform/observability/kube-prometheus-values.yaml" \
  --wait --timeout 12m
kubectl apply -f "$ROOT/platform/observability/dashboard-configmap.yaml"

echo "==> Installing ingress-nginx, cert-manager, External Secrets and Argo Rollouts"
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --version "$INGRESS_NGINX_CHART" \
  --values "$ROOT/platform/ingress-nginx-values.yaml" \
  --wait --timeout 10m
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version "$CERT_MANAGER_CHART" \
  --values "$ROOT/platform/cert-manager-values.yaml" \
  --wait --timeout 8m
helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace \
  --version "$EXTERNAL_SECRETS_CHART" \
  --values "$ROOT/platform/external-secrets-values.yaml" \
  --wait --timeout 8m
helm upgrade --install argo-rollouts argo/argo-rollouts \
  --namespace argo-rollouts --create-namespace \
  --version "$ARGO_ROLLOUTS_CHART" \
  --values "$ROOT/platform/argo-rollouts-values.yaml" \
  --wait --timeout 8m
kubectl apply -f "$ROOT/platform/security/cert-manager-issuers.yaml"

echo "==> Installing Loki and Promtail for structured log aggregation"
helm upgrade --install loki grafana/loki \
  --namespace monitoring \
  --version "$LOKI_CHART" \
  --values "$ROOT/platform/observability/loki-values.yaml" \
  --wait --timeout 10m
helm upgrade --install promtail grafana/promtail \
  --namespace monitoring \
  --version "$PROMTAIL_CHART" \
  --values "$ROOT/platform/observability/promtail-values.yaml" \
  --wait --timeout 8m

echo "==> Installing Kyverno policy engine"
helm upgrade --install kyverno kyverno/kyverno \
  --namespace kyverno --create-namespace \
  --version "$KYVERNO_CHART" \
  --values "$ROOT/platform/security/kyverno-values.yaml" \
  --wait --timeout 8m
kubectl wait --for=condition=available deployment -l app.kubernetes.io/name=kyverno -n kyverno --timeout=300s
kubectl apply -f "$ROOT/platform/security/kyverno-policies.yaml"

if [[ "$WITH_VELERO" == "true" ]]; then
  echo "==> Installing Velero (requires cloud placeholders to be replaced first)"
  helm upgrade --install velero vmware-tanzu/velero \
    --namespace velero --create-namespace \
    --version "$VELERO_CHART" \
    --values "$ROOT/platform/backup/velero-values.yaml" \
    --wait --timeout 10m
  kubectl apply -f "$ROOT/platform/backup/velero-schedule.yaml"
fi

echo "==> Building and loading taskflow:local"
docker build --build-arg VERSION=local --build-arg GIT_SHA="$(git rev-parse --short HEAD)" -t taskflow:local .
kind load docker-image taskflow:local --name "$KIND_CLUSTER"

echo "==> Applying the dev GitOps overlay"
kubectl delete job taskflow-migrate -n "$DEV_NS" --ignore-not-found
kubectl apply -k "$ROOT/deploy/gitops/environments/dev"
kubectl rollout status statefulset/taskflow-postgresql -n "$DEV_NS" --timeout=300s
kubectl wait --for=condition=complete job/taskflow-migrate -n "$DEV_NS" --timeout=300s
kubectl wait --for=condition=Ready pod -l app=taskflow -n "$DEV_NS" --timeout=300s

if [[ "$WITH_GITOPS" == "true" ]]; then
  echo "==> Installing Argo CD and the app-of-apps ApplicationSet"
  helm upgrade --install argocd argo/argo-cd \
    --namespace argocd --create-namespace \
    --version "$ARGO_CD_CHART" \
    --values "$ROOT/platform/argocd/argocd-values.yaml" \
    --wait --timeout 10m
  kubectl apply -f "$ROOT/platform/argocd/project.yaml"
  kubectl apply -f "$ROOT/platform/argocd/applicationset.yaml"
  echo "Argo CD bootstrap enabled. Staging/prod apps require AWS outputs and real secret ARNs."
fi

echo ""
echo "Local platform ready."
echo "  TaskFlow HTTP:  http://localhost:8080 (host taskflow.local)"
echo "  Grafana:        kubectl -n monitoring port-forward svc/kube-prometheus-grafana 3000:80"
echo "  Prometheus:     kubectl -n monitoring port-forward svc/prometheus-operated 9090:9090"
echo "  Verify:         make verify-platform"
echo "  Canary drill:   make canary-drill"
