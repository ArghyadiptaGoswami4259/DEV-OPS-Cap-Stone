#!/usr/bin/env bash
# Install locally usable platform tooling into .tools/ (ignored by Git).
#
# The sandbox permits github.com, codeload.github.com, api.github.com,
# registry.npmjs.org and pypi.org. Official release-asset hosts such as
# release-assets.githubusercontent.com, releases.hashicorp.com and dl.k8s.io
# are blocked, so this script uses source archives and bundled npm/PyPI wheels.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
BIN="$TOOLS/bin"
CACHE="$ROOT/.cache/toolchain"
PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"
NPM="$(command -v npm || true)"

mkdir -p "$BIN" "$CACHE" "$TOOLS/gopath" "$TOOLS/gocache"

if [[ ! -x "$PY" ]]; then
  echo "Run 'make install' first: $PY is missing." >&2
  exit 1
fi
if [[ -z "$NPM" ]]; then
  echo "npm is required to fetch bundled Helm/kubectl binaries." >&2
  exit 1
fi

fetch() {
  local url="$1" out="$2"
  curl -fsSL --retry 3 --max-time 180 -o "$out" "$url"
}

npm_pack() {
  local spec="$1" name
  name="$($NPM pack "$spec" --pack-destination "$CACHE" --silent 2>/dev/null | tail -n1)"
  if [[ -z "$name" || ! -f "$CACHE/$name" ]]; then
    echo "npm pack failed for $spec" >&2
    exit 1
  fi
  printf '%s' "$CACHE/$name"
}

printf '%s\n' '--- Go toolchain from PyPI wheel ---'
WHEEL="$(find "$CACHE" -maxdepth 1 -name 'go_bin-1.27.4-*.whl' | head -n1 || true)"
if [[ -z "$WHEEL" ]]; then
  "$PIP" download --no-deps --disable-pip-version-check -d "$CACHE" go-bin==1.27.4 >/dev/null
  WHEEL="$(find "$CACHE" -maxdepth 1 -name 'go_bin-1.27.4-*.whl' | head -n1)"
fi
rm -rf "$TOOLS/go"
mkdir -p "$TOOLS/go"
WHEEL="$WHEEL" DEST="$TOOLS/go" "$PY" - <<'PY'
import os
import zipfile
with zipfile.ZipFile(os.environ["WHEEL"]) as archive:
    archive.extractall(os.environ["DEST"])
PY
chmod +x "$TOOLS/go/go/bin/"* "$TOOLS/go/go/pkg/tool/linux_amd64/"*
ln -sf ../go/go/bin/go "$BIN/go"
ln -sf ../go/go/bin/gofmt "$BIN/gofmt"

export GOROOT="$TOOLS/go/go"
export GOPATH="$TOOLS/gopath"
export GOMODCACHE="$GOPATH/pkg/mod"
export GOCACHE="$TOOLS/gocache"
export PATH="$GOROOT/bin:$BIN:$PATH"
export GOTOOLCHAIN=local
export CGO_ENABLED=0
export GOSUMDB=off
export GOPRIVATE='*'
export GONOSUMDB='*'

printf '%s\n' '--- Python platform clients ---'
"$PIP" install --quiet --disable-pip-version-check -r "$ROOT/requirements-tools.txt"

printf '%s\n' '--- Helm binary from bundled npm package ---'
HELM_TGZ="$(npm_pack helm-binary-linux@3.10.1-1)"
tar -xzOf "$HELM_TGZ" package/bin/helm > "$BIN/helm"
chmod +x "$BIN/helm"

printf '%s\n' '--- kubectl binary from bundled AWS CDK layer ---'
KUBE_TGZ="$(npm_pack @aws-cdk/lambda-layer-kubectl-v31@2.1.0)"
KUBE_TGZ="$KUBE_TGZ" BIN="$BIN" "$PY" - <<'PY'
import io
import os
import tarfile
import zipfile

with tarfile.open(os.environ["KUBE_TGZ"]) as outer:
    layer = outer.extractfile("package/lib/layer.zip").read()
with zipfile.ZipFile(io.BytesIO(layer)) as inner:
    data = inner.read("kubectl/kubectl")
with open(os.path.join(os.environ["BIN"], "kubectl"), "wb") as stream:
    stream.write(data)
PY
chmod +x "$BIN/kubectl"

printf '%s\n' '--- kubectl-based kustomize and Python Sigstore wrappers ---'
cat > "$BIN/kustomize" <<'SH'
#!/bin/sh
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "${1:-}" = "build" ]; then shift; fi
exec "$here/kubectl" kustomize "$@"
SH
cat > "$BIN/sigstore" <<SH
#!/bin/sh
exec "$PY" -m sigstore "\$@"
SH
chmod +x "$BIN/kustomize" "$BIN/sigstore"

printf '%s\n' '--- Kind from source (local replacements for non-GitHub modules) ---'
KIND_BUILD="$CACHE/build/kind"
rm -rf "$KIND_BUILD"
mkdir -p "$KIND_BUILD/localmods"
fetch https://codeload.github.com/kubernetes-sigs/kind/tar.gz/refs/tags/v0.33.0 "$CACHE/kind-v0.33.0.tar.gz"
tar -xzf "$CACHE/kind-v0.33.0.tar.gz" -C "$KIND_BUILD" --strip-components=1

declare -A MOD_URLS=(
  [al.essio.dev/pkg/shellescape]='https://codeload.github.com/alessio/shellescape/tar.gz/refs/tags/v1.5.1'
  [go.yaml.in/yaml/v3]='https://codeload.github.com/yaml/go-yaml/tar.gz/refs/tags/v3.0.4'
  [golang.org/x/sys]='https://codeload.github.com/golang/sys/tar.gz/refs/tags/v0.6.0'
  [gopkg.in/check.v1]='https://codeload.github.com/go-check/check/tar.gz/038fdea0a05b'
  [gopkg.in/yaml.v3]='https://codeload.github.com/go-yaml/yaml/tar.gz/refs/tags/v3.0.1'
  [sigs.k8s.io/yaml]='https://codeload.github.com/kubernetes-sigs/yaml/tar.gz/refs/tags/v1.4.0'
)
for module in "${!MOD_URLS[@]}"; do
  safe="$(printf '%s' "$module" | tr '/.' '__')"
  dir="$KIND_BUILD/localmods/$safe"
  mkdir -p "$dir"
  fetch "${MOD_URLS[$module]}" "$KIND_BUILD/localmods/$safe.tar.gz"
  tar -xzf "$KIND_BUILD/localmods/$safe.tar.gz" -C "$dir" --strip-components=1
  if [[ ! -f "$dir/go.mod" ]]; then
    printf 'module %s\n\ngo 1.17\n' "$module" > "$dir/go.mod"
  fi
  (cd "$KIND_BUILD" && go mod edit -replace "$module=$dir")
done

(
  cd "$KIND_BUILD"
  export GOFLAGS=-mod=mod
  export GOPROXY=direct
  go mod download
  go build -trimpath -o "$BIN/kind" ./cmd/kind
)

printf '%s\n' '--- Docker CLI from vendored source ---'
DOCKER_BUILD="$CACHE/build/docker-cli"
rm -rf "$DOCKER_BUILD"
mkdir -p "$DOCKER_BUILD"
fetch https://codeload.github.com/docker/cli/tar.gz/refs/tags/v27.3.1 "$CACHE/docker-cli-v27.3.1.tar.gz"
tar -xzf "$CACHE/docker-cli-v27.3.1.tar.gz" -C "$DOCKER_BUILD" --strip-components=1
(
  cd "$DOCKER_BUILD"
  cp vendor.mod go.mod
  cp vendor.sum go.sum
  GOFLAGS=-mod=vendor GOPROXY=off GOSUMDB=off CGO_ENABLED=0 \
    go build -trimpath -o "$BIN/docker" ./cmd/docker
)

printf '%s\n' '--- Attempt official Terraform / Cosign binaries (hosts may be blocked) ---'
if curl -fsSL --max-time 20 -o "$CACHE/terraform.zip" \
  https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip; then
  unzip -oq "$CACHE/terraform.zip" -d "$BIN"
  chmod +x "$BIN/terraform"
  echo "Terraform binary installed."
else
  echo "Terraform binary host is blocked; HCL is validated with python-hcl2 instead."
fi
if curl -fsSL --max-time 20 -o "$BIN/cosign" \
  https://github.com/sigstore/cosign/releases/download/v2.4.1/cosign-linux-amd64; then
  chmod +x "$BIN/cosign"
  echo "Cosign binary installed."
else
  rm -f "$BIN/cosign"
  echo "Cosign release-asset host is blocked; Python Sigstore client is available instead."
fi

cat > "$TOOLS/README.md" <<'EOF'
# Local platform toolchain

Generated by `make tools`. This directory is ignored by Git because it contains
large binaries and module caches.

Obtained from allowlisted sources:
- Go 1.27.4 (`go-bin` PyPI wheel)
- Helm 3.10.1 (bundled npm binary)
- kubectl 1.31.9 with `kubectl kustomize` v5.4.2 (bundled AWS CDK layer)
- Kind 0.33.0 (built from source with local module replacements)
- Docker CLI 27.3.1 (built from vendored source)
- Python clients: Sigstore, Kubernetes and Docker SDKs
- `sigstore` and `kustomize` command wrappers

Not available in this sandbox:
- Docker daemon / container runtime (no socket, no installable apt packages)
- Native Terraform binary (releases.hashicorp.com is blocked)
- Native Cosign binary (GitHub release-asset host is blocked)
- A live Kubernetes cluster (requires Docker/Podman/containerd and kernel privileges)

The CI/CD workflows still use official pinned actions for Terraform, Cosign,
Docker, Helm and Kubernetes in a real runner.
EOF

printf '%s\n' '--- local toolchain check ---'
"$PY" "$ROOT/tools/check-platform-tools.py"
