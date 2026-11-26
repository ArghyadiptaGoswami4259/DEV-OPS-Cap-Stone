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

## Still unavailable in this sandbox

- **Docker daemon / container runtime**: no `/var/run/docker.sock`, no installable `docker.io`,
  `containerd`, `runc` or Podman packages, and privileged kernel networking is not available.
- **Live Kubernetes cluster**: Kind requires Docker, Podman or a working containerd/nerdctl runtime.
  `kubectl`, Helm and Kustomize manifests can still be rendered and validated locally.
- **Native Terraform binary**: the official HashiCorp release host is blocked. HCL syntax is still
  parsed by `python-hcl2` inside `tools/validate_repo.py`.
- **Native Cosign binary**: GitHub release assets redirect to a blocked host. The Python Sigstore
  client is installed as a verification fallback; CI still uses the pinned Cosign installer action.

## Usage

```bash
make install       # creates .venv with runtime/dev/tool client dependencies
make tools         # builds .tools/ from allowlisted sources
make tools-check   # verifies binaries, wrappers, Python clients and Kustomize rendering
make validate      # parses manifests and checks shell syntax, among other checks
```

To use the tools directly:

```bash
export PATH="$PWD/.tools/bin:$PATH"
helm version --short
kubectl version --client
kustomize build deploy/gitops/environments/dev
kind version
docker --version
```

The CI/CD workflows do not depend on `.tools/`; they use pinned official GitHub Actions and
runner-provided tooling for Docker, Cosign, Terraform, Helm and Kubernetes.
