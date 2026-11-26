# Docker-independent local runtime

TaskFlow's normal local Kubernetes path (`make kind-up`) expects a Docker daemon.
That is the right choice for a normal workstation, but it is not available in the
development sandbox. This repository therefore includes a reproducible
source-based runtime that uses **rootful Podman + containerd + runc + a local
Kubernetes control plane** instead. It is used to prove image building, image
importing, Pod scheduling, container execution, API readiness and component
health without claiming that Docker/Compose, Kind or Argo CD were run.

> This is a validation cluster, not a production Kubernetes distribution. It uses
> a loopback API address, generated local certificates, permissive local
> authorization, a ptp CNI configuration and scratch probe images. Do not expose
> it outside the sandbox or reuse its bootstrap for a real cluster.

## Prerequisites

Run the existing Python and base-tool installers first:

```bash
make install
make tools
```

The runtime builder needs the local Go toolchain from `make tools`, plus `gcc`,
`ar`, `curl`, `tar`, `ip` and passwordless `sudo -n`. It downloads only pinned
source archives from `codeload.github.com` into ignored `.cache/toolchain/`.
Generated source trees, Go caches, binaries, libraries and cluster state stay in
ignored `.tools/` and `.cache/` directories and are not committed.

## Build and verify binaries

```bash
make local-runtime
make local-runtime-check
```

`make local-runtime` builds these pinned components when they are missing:

| Component | Version | Purpose |
|---|---:|---|
| Podman | 5.2.5 | Build and save local OCI images |
| conmon | 2.1.12 | OCI container monitor for Podman |
| GLib header synthesis | 2.74.6 | Supplies the generated Meson header needed by conmon |
| libseccomp | 2.5.5 | Static seccomp library for runc |
| runc | 1.1.14 | OCI runtime, built with the `seccomp` tag |
| CNI plugins | 1.5.1 | Pod networking, ptp and port mapping |
| containerd / ctr / shim | 1.7.20 | CRI runtime used by kubelet |
| etcd | 3.5.16 | Kubernetes API datastore |
| Kubernetes | 1.31.0 | API server, controller-manager, scheduler, kubelet, kubeadm, kubectl and kube-proxy |

The builder is idempotent: each component has a small version probe, so an
already-installed binary that reports its expected version is skipped. It never
downloads release binaries from blocked hosts and does not require the Docker
daemon, GitHub Actions, Terraform or Cosign.

## Start and verify the local cluster

```bash
make local-cluster-up
make local-cluster-check
make local-cluster-down
```

`tools/local-cluster.sh` performs these steps:

1. Creates local container, storage, CNI, containerd, kubeadm and kubelet
   configuration under `.cache/taskflow-local-cluster/`.
2. Adds `10.10.0.1/24` to the loopback interface and a matching hostname entry
   so locally generated certificates have a stable SAN.
3. Generates a fresh kubeadm bootstrap token at runtime, then uses the locally built `kubeadm` to
   generate certificates and kubeconfigs.
4. Starts etcd, containerd, kube-apiserver, controller-manager, scheduler and
   kubelet from the source-built binaries. etcd listens on loopback HTTP; the
   Kubernetes API uses kubeadm-generated TLS certificates.
5. Compiles two tiny static scratch images with Podman: a pause image and a
   hello probe. Each image is saved separately and imported into containerd.
6. Waits for the node to become Ready and for the controller-manager to create
   the `default` ServiceAccount, then applies `taskflow-runtime-probe` and waits
   for it to succeed.
7. Leaves logs, certificates and kubeconfigs in the ignored cluster state
   directory for inspection.

`make local-cluster-check` verifies:

- `/readyz` returns `ok` using the generated admin client certificate;
- one node is `Ready` and reports a `containerd://` runtime;
- etcd, controller-manager and scheduler component statuses are `Healthy`;
- `taskflow-runtime-probe` is `Succeeded`, has a pod IP, and prints
  `hello from rootful podman` in its logs.

`make local-cluster-down` stops the locally started processes. It does not
remove generated state, so the kubeconfig and logs remain available for
troubleshooting; delete `.cache/taskflow-local-cluster/` manually for a clean
bootstrap.

## Security and scope notes

- Rootful Podman is used because the sandbox lacks `newuidmap`/rootless user
  namespace helpers. The Podman policy is local-only and accepts locally built
  images.
- The probe Pod requests `seccompProfile: Unconfined` because the sandbox's
  seccomp behavior differs from a normal Kubernetes node; the runc binary is
  still built with libseccomp support.
- API server authorization is `AlwaysAllow` and `NodeRestriction` is disabled
  because this is a single-user, isolated validation control plane. etcd is
  loopback-only HTTP. Production manifests in the repository keep their normal
  admission, authorization and TLS posture.
- The loopback address, generated certificates, loopback etcd endpoint and local
  scratch images are intentionally not portable cloud resources.
- Argo CD, Argo Rollouts, Alertmanager delivery, Velero/RDS restore, Terraform
  apply, Cosign verification and live GitHub Actions are outside this local
  validation path.

See [validation evidence](validation-evidence.md) for exact command results.
