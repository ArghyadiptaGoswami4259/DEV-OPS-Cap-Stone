#!/usr/bin/env bash
# Reproducible Docker-independent TaskFlow control plane bootstrap.
# This is a local validation cluster, not a production Kubernetes distribution.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/.tools/bin"
K8S="$BIN/k8s"
CONTAINERD="$BIN/containerd-bin"
CNI="$BIN/cni"
CLUSTER="$ROOT/.cache/taskflow-local-cluster"
CERTS="$CLUSTER/certs"
KUBECONFIG_DIR="$CLUSTER/kubeconfig"
IMAGES="$CLUSTER/images"
LOGS="$CLUSTER/logs"
KUBECONFIG="$KUBECONFIG_DIR/admin.conf"
SOCKET="$CLUSTER/containerd/containerd.sock"
API_IP="10.10.0.1"
ETCD_URL="http://127.0.0.1:2379"
POD_CIDR="10.244.0.0/16"
SERVICE_CIDR="10.96.0.0/12"
CLUSTER_DNS="10.96.0.10"
NODE_NAME="taskflow-local"
SUDO=(sudo -n)
BOOTSTRAP_TOKEN=""

require() {
  if [[ ! -x "$1" ]]; then
    echo "Missing runtime binary: $1" >&2
    echo "Run 'make local-runtime' first." >&2
    exit 1
  fi
}

for command_name in gcc ar curl head od sudo ip tr; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required local command is missing: $command_name" >&2
    exit 1
  fi
done
require "$BIN/podman"
require "$BIN/conmon"
require "$BIN/runc"
require "$BIN/etcd"
require "$K8S/kube-apiserver"
require "$K8S/kube-controller-manager"
require "$K8S/kube-scheduler"
require "$K8S/kubelet"
require "$K8S/kubeadm"
require "$K8S/kubectl"
require "$CONTAINERD/containerd"
require "$CONTAINERD/ctr"
require "$CONTAINERD/containerd-shim-runc-v2"
require "$CNI/ptp"
require "$CNI/host-local"
require "$CNI/loopback"

generate_bootstrap_token() {
  local first second
  first="$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  second="$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  printf '%s.%s' "$first" "$second"
}

export PATH="$BIN:$K8S:$CONTAINERD:$PATH"
export CONTAINERS_CONF="$ROOT/.tools/etc/containers/containers.conf"
export CONTAINERS_STORAGE_CONF="$ROOT/.tools/etc/containers/storage.conf"
export CONTAINERS_POLICY="$ROOT/.tools/etc/containers/policy.json"

write_static_files() {
  "${SUDO[@]}" rm -rf "$CLUSTER/etcd" "$CLUSTER/containerd/root" \
    "$CLUSTER/containerd/state" "$CLUSTER/containers" "$SOCKET"
  mkdir -p "$CERTS" "$KUBECONFIG_DIR" "$IMAGES" "$LOGS" "$CLUSTER/kubelet/pki" \
    "$CLUSTER/containerd" "$CLUSTER/cni" "$CLUSTER/manifests" \
    "$ROOT/.tools/etc/containers" "$ROOT/.tools/etc/cni/net.d"
  cat > "$ROOT/.tools/etc/containers/policy.json" <<'POLICY'
{"default":[{"type":"insecureAcceptAnything"}]}
POLICY
  cat > "$ROOT/.tools/etc/containers/storage.conf" <<EOF
[storage]
driver = "vfs"
runroot = "$CLUSTER/containers/run"
graphroot = "$CLUSTER/containers/graph"
[storage.options.vfs]
ignore_chown_errors = "true"
EOF
  cat > "$ROOT/.tools/etc/containers/containers.conf" <<EOF
[containers]
runtime = "$BIN/runc"
runtime_supports_json = ["runc", "crun"]
[engine]
conmon_path = ["$BIN/conmon"]
cni_plugin_dirs = ["$CNI"]
[network]
network_backend = "cni"
EOF
  "${SUDO[@]}" mkdir -p /etc/containers
  "${SUDO[@]}" cp "$ROOT/.tools/etc/containers/policy.json" /etc/containers/policy.json
  cat > "$CLUSTER/containerd/config.toml" <<EOF
version = 2
root = "$CLUSTER/containerd/root"
state = "$CLUSTER/containerd/state"
[grpc]
  address = "$SOCKET"
  uid = 0
  gid = 0
[plugins."io.containerd.grpc.v1.cri"]
  sandbox_image = "localhost/taskflow/pause:local"
  unset_seccomp_profile = "unconfined"
  [plugins."io.containerd.grpc.v1.cri".containerd]
    default_runtime_name = "runc"
    [plugins."io.containerd.grpc.v1.cri".containerd.runtimes]
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc]
        runtime_type = "io.containerd.runc.v2"
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
          BinaryName = "$BIN/runc"
          SystemdCgroup = false
  [plugins."io.containerd.grpc.v1.cri".cni]
    bin_dir = "$CNI"
    conf_dir = "$CLUSTER/cni"
EOF
  cat > "$CLUSTER/cni/10-taskflow-ptp.conflist" <<CNI_CONFIG
{
  "cniVersion": "1.0.0",
  "name": "taskflow-ptp",
  "plugins": [
    {
      "type": "ptp",
      "mtu": 1500,
      "ipam": {
        "type": "host-local",
        "ranges": [[{"subnet": "$POD_CIDR"}]],
        "routes": [{"dst": "0.0.0.0/0"}]
      }
    },
    {"type": "loopback"}
  ]
}
CNI_CONFIG
  cat > "$CLUSTER/kubeadm.yaml" <<EOF
apiVersion: kubeadm.k8s.io/v1beta4
kind: InitConfiguration
bootstrapTokens:
- groups:
  - system:bootstrappers:kubeadm:default-node-token
  token: $BOOTSTRAP_TOKEN # gitleaks:allow
  ttl: 24h0m0s
  usages:
  - signing
  - authentication
localAPIEndpoint:
  advertiseAddress: $API_IP
  bindPort: 6443
nodeRegistration:
  criSocket: unix://$SOCKET
  imagePullPolicy: IfNotPresent
  imagePullSerial: true
  name: $NODE_NAME
  taints: null
timeouts:
  controlPlaneComponentHealthCheck: 4m0s
  discovery: 5m0s
  etcdAPICall: 2m0s
  kubeletHealthCheck: 4m0s
  kubernetesAPICall: 1m0s
  tlsBootstrap: 5m0s
  upgradeManifests: 5m0s
---
apiVersion: kubeadm.k8s.io/v1beta4
kind: ClusterConfiguration
kubernetesVersion: v1.31.0
clusterName: taskflow-local
certificatesDir: $CERTS
imageRepository: localhost/taskflow
controlPlaneEndpoint: $API_IP:6443
apiServer:
  certSANs:
  - $API_IP
  - 127.0.0.1
  - localhost
  - $NODE_NAME
  - kubernetes
  - kubernetes.default
  - kubernetes.default.svc
  - kubernetes.default.svc.cluster.local
networking:
  dnsDomain: cluster.local
  serviceSubnet: $SERVICE_CIDR
  podSubnet: $POD_CIDR
etcd:
  local:
    dataDir: $CLUSTER/etcd
EOF
  cat > "$CLUSTER/probe-pod.yaml" <<'PROBE'
apiVersion: v1
kind: Pod
metadata:
  name: taskflow-runtime-probe
  namespace: default
  labels:
    app: taskflow-runtime-probe
spec:
  restartPolicy: Never
  dnsPolicy: Default
  terminationGracePeriodSeconds: 1
  securityContext:
    seccompProfile:
      type: Unconfined
  containers:
  - name: probe
    image: localhost/taskflow/probe:local
    imagePullPolicy: Never
    securityContext:
      seccompProfile:
        type: Unconfined
PROBE
}

generate_certs() {
  # kubeadm writes a temporary directory below /etc/kubernetes even when the
  # generated kubeconfigs are redirected. Keep that local-only path owned by
  # the invoking user so the rest of the bootstrap stays unprivileged.
  "${SUDO[@]}" mkdir -p /etc/kubernetes
  "${SUDO[@]}" chown -R "$(id -u):$(id -g)" /etc/kubernetes
  rm -rf "$CERTS"
  mkdir -p "$CERTS"
  rm -f "$KUBECONFIG_DIR"/*.conf
  "$K8S/kubeadm" init phase certs all \
    --config "$CLUSTER/kubeadm.yaml" >/dev/null
  "$K8S/kubeadm" init phase kubeconfig all \
    --config "$CLUSTER/kubeadm.yaml" \
    --kubeconfig-dir "$KUBECONFIG_DIR" >/dev/null
}

build_kubelet_config() {
  cat > "$CLUSTER/kubelet/config.yaml" <<EOF
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
address: 0.0.0.0
authentication:
  anonymous:
    enabled: false
  webhook:
    cacheTTL: 2m0s
    enabled: true
  x509:
    clientCAFile: $CERTS/ca.crt
authorization:
  mode: Webhook
  webhook:
    cacheAuthorizedTTL: 5m0s
    cacheUnauthorizedTTL: 30s
cgroupDriver: cgroupfs
cgroupsPerQOS: true
clusterDNS:
- $CLUSTER_DNS
clusterDomain: cluster.local
containerRuntimeEndpoint: unix://$SOCKET
cpuManagerReconcilePeriod: 10s
enableControllerAttachDetach: true
enableDebuggingHandlers: true
enableServer: true
enforceNodeAllocatable:
- pods
eventBurst: 100
eventRecordQPS: 50
evictionHard:
  imagefs.available: "5%"
  memory.available: 100Mi
  nodefs.available: "5%"
  nodefs.inodesFree: "5%"
evictionPressureTransitionPeriod: 5m0s
failSwapOn: false
fileCheckFrequency: 20s
hairpinMode: none
healthzBindAddress: 127.0.0.1
healthzPort: 10248
httpCheckFrequency: 20s
imageGCHighThresholdPercent: 85
imageGCLowThresholdPercent: 80
imageMinimumGCAge: 2m0s
logging:
  flushFrequency: 5s
  options:
    json:
      infoBufferSize: "0"
    text:
      infoBufferSize: "0"
  verbosity: 2
maxPods: 110
memorySwap: {}
nodeStatusReportFrequency: 5m0s
nodeStatusUpdateFrequency: 10s
podPidsLimit: -1
registerNode: true
resolvConf: /etc/resolv.conf
rotateCertificates: false
runtimeRequestTimeout: 15m
seccompDefault: false
serializeImagePulls: false
staticPodPath: $CLUSTER/manifests
streamingConnectionIdleTimeout: 4h
syncFrequency: 1m
volumeStatsAggPeriod: 1m
EOF
}

build_images() {
  local hello="$IMAGES/hello-root"
  local pause="$IMAGES/pause-root"
  "${SUDO[@]}" rm -rf "$hello" "$pause" "$IMAGES/hello.tar" \
    "$IMAGES/pause.tar" "$IMAGES/probe.tar"
  mkdir -p "$hello" "$pause"
  cat > "$hello/hello.c" <<'C'
#include <unistd.h>
int main(void) {
  const char message[] = "hello from rootful podman\n";
  return write(1, message, sizeof(message) - 1) ==
    (ssize_t)(sizeof(message) - 1) ? 0 : 1;
}
C
  gcc -static -O2 "$hello/hello.c" -o "$hello/hello"
  cat > "$hello/Dockerfile" <<'DOCKER'
FROM scratch
COPY hello /hello
ENTRYPOINT ["/hello"]
DOCKER
  cat > "$pause/pause.c" <<'C'
#include <unistd.h>
int main(void) { for (;;) pause(); return 0; }
C
  gcc -static -O2 "$pause/pause.c" -o "$pause/pause"
  cat > "$pause/Dockerfile" <<'DOCKER'
FROM scratch
COPY pause /pause
ENTRYPOINT ["/pause"]
DOCKER
  "${SUDO[@]}" env PATH="$PATH" CONTAINERS_CONF="$CONTAINERS_CONF" \
    CONTAINERS_STORAGE_CONF="$CONTAINERS_STORAGE_CONF" CONTAINERS_POLICY="$CONTAINERS_POLICY" \
    "$BIN/podman" build --security-opt seccomp=unconfined \
    -t localhost/taskflow/probe:local "$hello" >/dev/null
  "${SUDO[@]}" env PATH="$PATH" CONTAINERS_CONF="$CONTAINERS_CONF" \
    CONTAINERS_STORAGE_CONF="$CONTAINERS_STORAGE_CONF" CONTAINERS_POLICY="$CONTAINERS_POLICY" \
    "$BIN/podman" build --security-opt seccomp=unconfined \
    -t localhost/taskflow/pause:local "$pause" >/dev/null
  "${SUDO[@]}" env PATH="$PATH" CONTAINERS_CONF="$CONTAINERS_CONF" \
    CONTAINERS_STORAGE_CONF="$CONTAINERS_STORAGE_CONF" CONTAINERS_POLICY="$CONTAINERS_POLICY" \
    "$BIN/podman" save -o "$IMAGES/probe.tar" localhost/taskflow/probe:local >/dev/null
  "${SUDO[@]}" env PATH="$PATH" CONTAINERS_CONF="$CONTAINERS_CONF" \
    CONTAINERS_STORAGE_CONF="$CONTAINERS_STORAGE_CONF" CONTAINERS_POLICY="$CONTAINERS_POLICY" \
    "$BIN/podman" save -o "$IMAGES/pause.tar" localhost/taskflow/pause:local >/dev/null
  "${SUDO[@]}" chmod 644 "$IMAGES/probe.tar" "$IMAGES/pause.tar"
  "${SUDO[@]}" "$CONTAINERD/ctr" --address "$SOCKET" -n k8s.io images import \
    --local --digests --skip-digest-for-named "$IMAGES/pause.tar" >/dev/null
  "${SUDO[@]}" "$CONTAINERD/ctr" --address "$SOCKET" -n k8s.io images import \
    --local --digests --skip-digest-for-named "$IMAGES/probe.tar" >/dev/null
  "${SUDO[@]}" "$CONTAINERD/ctr" --address "$SOCKET" -n k8s.io images ls \
    >"$LOGS/ctr.log" 2>&1
}

wait_for_etcd() {
  for _ in $(seq 1 60); do
    if curl -fsS "$ETCD_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "etcd did not become healthy; see $LOGS/etcd.log" >&2
  return 1
}

wait_for_socket() {
  local socket="$1"
  local name="$2"
  for _ in $(seq 1 120); do
    if [[ -S "$socket" ]]; then
      "${SUDO[@]}" chmod 666 "$socket" || true
      return 0
    fi
    sleep 0.25
  done
  echo "$name socket did not appear: $socket" >&2
  return 1
}

wait_for_api() {
  for _ in $(seq 1 120); do
    if "$K8S/kubectl" --kubeconfig "$KUBECONFIG" --request-timeout=2s \
        get --raw=/readyz 2>/dev/null | grep -qx ok; then
      return 0
    fi
    sleep 0.5
  done
  echo "Kubernetes API did not become ready; see $LOGS/" >&2
  return 1
}

wait_for_node_ready() {
  for _ in $(seq 1 120); do
    local state
    state="$($K8S/kubectl --kubeconfig "$KUBECONFIG" --request-timeout=2s \
      get node "$NODE_NAME" \
      -o 'jsonpath={.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
    if [[ "$state" == "True" ]]; then
      return 0
    fi
    sleep 0.5
  done
  echo "Node $NODE_NAME did not become Ready; see $LOGS/kubelet.log" >&2
  return 1
}

wait_for_default_serviceaccount() {
  for _ in $(seq 1 120); do
    if "$K8S/kubectl" --kubeconfig "$KUBECONFIG" --request-timeout=2s \
        get serviceaccount default -n default >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "default ServiceAccount was not created; see $LOGS/controller-manager.log" >&2
  return 1
}

start_process() {
  local name="$1"
  shift
  "${SUDO[@]}" nohup "$@" >"$LOGS/$name.log" 2>&1 &
  echo "$!" >"$CLUSTER/$name.pid"
}

up() {
  BOOTSTRAP_TOKEN="$(generate_bootstrap_token)"
  write_static_files
  if ! ip -4 addr show lo | grep -q "$API_IP/24"; then
    "${SUDO[@]}" ip addr add "$API_IP/24" dev lo
  fi
  if ! grep -q "$API_IP $NODE_NAME" /etc/hosts; then
    printf '%s %s\n' "$API_IP" "$NODE_NAME" | "${SUDO[@]}" tee -a /etc/hosts >/dev/null
  fi
  generate_certs
  build_kubelet_config
  start_process etcd "$BIN/etcd" \
    --name "$NODE_NAME" \
    --data-dir "$CLUSTER/etcd" \
    --listen-client-urls "$ETCD_URL" \
    --advertise-client-urls "$ETCD_URL" \
    --listen-peer-urls http://127.0.0.1:2380 \
    --initial-advertise-peer-urls http://127.0.0.1:2380 \
    --initial-cluster "$NODE_NAME=http://127.0.0.1:2380" \
    --initial-cluster-state new \
    --initial-cluster-token taskflow-local \
    --log-level info
  wait_for_etcd
  start_process containerd "$CONTAINERD/containerd" \
    --config "$CLUSTER/containerd/config.toml" --log-level info
  wait_for_socket "$SOCKET" containerd
  build_images
  start_process kube-apiserver "$K8S/kube-apiserver" \
    --advertise-address "$API_IP" \
    --bind-address 0.0.0.0 \
    --secure-port 6443 \
    --etcd-servers "$ETCD_URL" \
    --service-cluster-ip-range "$SERVICE_CIDR" \
    --service-node-port-range 30000-32767 \
    --authorization-mode AlwaysAllow \
    --enable-admission-plugins ServiceAccount \
    --disable-admission-plugins NodeRestriction \
    --client-ca-file "$CERTS/ca.crt" \
    --tls-cert-file "$CERTS/apiserver.crt" \
    --tls-private-key-file "$CERTS/apiserver.key" \
    --kubelet-client-certificate "$CERTS/apiserver-kubelet-client.crt" \
    --kubelet-client-key "$CERTS/apiserver-kubelet-client.key" \
    --service-account-key-file "$CERTS/sa.pub" \
    --service-account-signing-key-file "$CERTS/sa.key" \
    --service-account-issuer https://kubernetes.default.svc.cluster.local \
    --api-audiences https://kubernetes.default.svc.cluster.local \
    --requestheader-client-ca-file "$CERTS/front-proxy-ca.crt" \
    --requestheader-allowed-names front-proxy-client \
    --proxy-client-cert-file "$CERTS/front-proxy-client.crt" \
    --proxy-client-key-file "$CERTS/front-proxy-client.key" \
    --enable-aggregator-routing=true \
    --allow-privileged=true \
    --runtime-config api/all=true \
    --v=2
  wait_for_api
  start_process controller-manager "$K8S/kube-controller-manager" \
    --kubeconfig "$KUBECONFIG" \
    --leader-elect=false \
    --use-service-account-credentials=true \
    --controllers '*,bootstrapsigner,tokencleaner' \
    --allocate-node-cidrs=true \
    --cluster-cidr "$POD_CIDR" \
    --node-cidr-mask-size=24 \
    --service-cluster-ip-range "$SERVICE_CIDR" \
    --cluster-name taskflow-local \
    --root-ca-file "$CERTS/ca.crt" \
    --service-account-private-key-file "$CERTS/sa.key" \
    --cluster-signing-cert-file "$CERTS/ca.crt" \
    --cluster-signing-key-file "$CERTS/ca.key" \
    --bind-address 127.0.0.1 \
    --secure-port 10257 \
    --v=2
  start_process scheduler "$K8S/kube-scheduler" \
    --kubeconfig "$KUBECONFIG" \
    --leader-elect=false \
    --bind-address 127.0.0.1 \
    --secure-port 10259 \
    --v=2
  start_process kubelet "$K8S/kubelet" \
    --config "$CLUSTER/kubelet/config.yaml" \
    --kubeconfig "$KUBECONFIG_DIR/kubelet.conf" \
    --cert-dir "$CLUSTER/kubelet/pki" \
    --root-dir "$CLUSTER/kubelet" \
    --hostname-override "$NODE_NAME" \
    --node-ip "$API_IP" \
    --container-runtime-endpoint "unix://$SOCKET" \
    --cgroup-driver cgroupfs \
    --fail-swap-on=false \
    --register-node=true \
    --anonymous-auth=false \
    --authorization-mode Webhook \
    --authentication-token-webhook=true \
    --client-ca-file "$CERTS/ca.crt" \
    --read-only-port=0 \
    --rotate-certificates=false \
    --cluster-dns "$CLUSTER_DNS" \
    --cluster-domain cluster.local \
    --hairpin-mode none \
    --runtime-request-timeout 15m \
    --v=2
  wait_for_node_ready
  wait_for_default_serviceaccount
  "$K8S/kubectl" --kubeconfig "$KUBECONFIG" --request-timeout=10s \
    delete pod taskflow-runtime-probe --ignore-not-found --wait=false >/dev/null
  "$K8S/kubectl" --kubeconfig "$KUBECONFIG" --request-timeout=10s \
    apply -f "$CLUSTER/probe-pod.yaml" >/dev/null
  local phase=""
  for _ in $(seq 1 120); do
    phase="$($K8S/kubectl --kubeconfig "$KUBECONFIG" --request-timeout=2s \
      get pod taskflow-runtime-probe -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    if [[ "$phase" == "Succeeded" || "$phase" == "Failed" ]]; then
      break
    fi
    sleep 0.5
  done
  if [[ "$phase" != "Succeeded" ]]; then
    echo "Runtime probe did not succeed (phase: ${phase:-unknown}); see $LOGS/" >&2
    "$K8S/kubectl" --kubeconfig "$KUBECONFIG" describe pod taskflow-runtime-probe >&2 || true
    return 1
  fi
  echo "Local cluster started. Run 'make local-cluster-check'."
}

stop_process() {
  local name="$1"
  local pid_file="$CLUSTER/$name.pid"
  if [[ -f "$pid_file" ]]; then
    "${SUDO[@]}" kill "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file"
  fi
}

down() {
  for name in kubelet scheduler controller-manager kube-apiserver containerd etcd; do
    stop_process "$name"
  done
  "${SUDO[@]}" pkill -f "$CLUSTER" 2>/dev/null || true
  "${SUDO[@]}" rm -f "$SOCKET"
  echo "Local cluster stopped; logs and generated certificates remain in $CLUSTER."
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *)
    echo "Usage: $0 {up|down}" >&2
    exit 2
    ;;
esac
