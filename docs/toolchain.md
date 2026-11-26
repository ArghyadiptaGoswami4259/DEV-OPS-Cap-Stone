# Local platform toolchain

`make tools` installs a locally usable DevOps toolchain into `.tools/`. That directory is ignored
by Git because it contains large binaries, a Go toolchain and build caches. `make tools-check`
verifies the result.

## Why an installer is needed

This development sandbox allows outbound access only to `github.com`, `codeload.github.com`,
`api.github.com`, `registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org`. The usual binary
download hosts are blocked:

| Host | Used for | Status |
|---|---|---|
| `release-assets.githubusercontent.com` | GitHub release binaries such as Kind/Cosign | Blocked |
| `releases.hashicorp.com` | Terraform binary | Blocked |
| `dl.k8s.io`, `get.helm.sh` | kubectl/Helm binaries | Blocked |
| `download.docker.com`, Debian mirrors | Docker daemon/container runtime | Blocked |

The installer therefore uses only allowlisted sources: source archives from `codeload.github.com`,
bundled binaries in npm packages, and a Go toolchain distributed as a PyPI wheel.

## Installed locally

| Tool | Version / source | Notes |
|---|---|---|
| Go | 1.27.4 from the `go-bin` PyPI wheel | Used to compile Kind and Docker CLI |
| Helm | 3.10.1 from `helm-binary-linux` npm package | Real Linux binary |
| kubectl | 1.31.9 from `@aws-cdk/lambda-layer-kubectl-v31` | Real Linux binary; includes Kustomize v5.4.2 |
| kustomize | `kubectl kustomize` wrapper | Supports `kustomize build <dir>` |
| Kind | 0.33.0 built from source | Non-GitHub Go modules are replaced with local codeload checkouts |
| Docker CLI | 27.3.1 built from vendored `docker/cli` source | Client only; no daemon is available |
| Sigstore CLI | `python -m sigstore` wrapper | Python client, not a drop-in Cosign binary |
| Python SDKs | `sigstore`, `kubernetes`, `docker` | Installed from `requirements-tools.txt` |

## Docker-independent runtime

`make local-runtime` builds the missing container and Kubernetes runtime from pinned
`codeload.github.com` source archives into the same ignored `.tools/` directory. It uses the local
Go toolchain and avoids blocked release-asset hosts. `make local-runtime-check` verifies binaries
offline; `make local-cluster-check` verifies a live local control plane.

| Component | Version / source | Notes |
|---|---|---|
| Podman | 5.2.5 source, CGO-enabled build | Rootful local image build/save; no Docker daemon needed |
| conmon | 2.1.12 source | Built against GLib 2.74.6 headers synthesized from source and the system GLib shared object |
| libseccomp | 2.5.5 source | Static library and `pkg-config` shim generated without autoconf/gperf |
| runc | 1.1.14 source with `seccomp` tag | Links the local static libseccomp |
| CNI plugins | 1.5.1 source | Bridge, ptp, loopback, host-local, portmap and related plugins |
| containerd / ctr | 1.7.20 vendored source | CRI runtime used by kubelet |
| etcd | 3.5.16 source | Built with local module replacements sourced from vendored Kubernetes/container trees |
| Kubernetes | 1.31.0 source | `kube-apiserver`, controller-manager, scheduler, kubelet, kubeadm, kubectl and kube-proxy; built with offline local module replacements |
| Local images | scratch pause and hello probe | Built from source, saved as separate Docker archives and imported into containerd |

See `docs/local-runtime.md` for exact commands and `docs/validation-evidence.md` for the verified
results. The runtime is for local validation only; production clusters should use a supported
Kubernetes distribution.

## Still unavailable in this sandbox

- **Docker daemon / Compose and Kind-on-Docker paths**: no `/var/run/docker.sock` and no installable
  Docker daemon package. The Docker CLI remains available, but Compose and `make kind-up` require a
  daemon.
- **Native Terraform binary**: the official HashiCorp release host is blocked. HCL syntax is still
  parsed by `python-hcl2` inside `tools/validate_repo.py`.
- **Native Cosign binary**: GitHub release assets redirect to a blocked host. The Python Sigstore
  client is installed as a verification fallback; CI still uses the pinned Cosign installer action.
- **Cloud/in-cluster integrations**: AWS provisioning, Argo CD/Rollouts in-cluster behavior,
  Alertmanager delivery, Velero/RDS restore and production CD/promotion workflows require a real
  account or runner. GitHub Actions PR CI checks run remotely on pull requests.

## Usage

```bash
make install              # creates .venv with runtime/dev/tool client dependencies
make tools                # builds .tools/ from allowlisted sources
make tools-check          # verifies base binaries, wrappers, Python clients and Kustomize rendering
make configure            # renders platform values from config/platform.env
make configure-check      # verifies configured manifests are synchronized
make local-runtime        # builds the Docker-independent runtime from source
make local-runtime-check  # verifies the runtime binaries offline
make local-cluster-up     # starts a local Docker-independent Kubernetes control plane
make local-cluster-check  # validates readiness, node health, Pod scheduling and logs
make local-cluster-down   # stops the local control plane
make validate             # parses manifests and checks shell syntax, among other checks
```

To use the tools directly:

```bash
export PATH="$PWD/.tools/bin:$PWD/.tools/bin/k8s:$PWD/.tools/bin/containerd-bin:$PATH"
helm version --short
kubectl version --client
kustomize build deploy/gitops/environments/dev
kind version
docker --version
podman --version
runc --version
etcd --version
containerd --version
```

The CI/CD workflows do not depend on `.tools/`; they use pinned official GitHub Actions and
runner-provided tooling for Docker, Cosign, Terraform, Helm and Kubernetes.
