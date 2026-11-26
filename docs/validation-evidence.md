# Validation evidence

This page records exact local checks for the TaskFlow capstone. It distinguishes
repository-level results from runtime results and from operations that require a
real cloud, CI runner or production cluster. Commands are shown from the
repository root on branch `arena/ff437085-dev-ops-cap-stone`.

## Repository gates

| Gate | Result |
|---|---|
| `make lint` | Ruff: `All checks passed!`; MyPy: `Success: no issues found in 12 source files`; Bandit: no issues; `pip-audit --strict`: `No known vulnerabilities found`. |
| `make test` | `11 passed`. |
| `make configure-check` | `Platform configuration is synchronized.` |
| `make validate` | Required files, Python/shell, YAML/JSON/HCL, Kustomize references, pinned action SHAs, secret heuristics, synchronized platform configuration, lab-manual student details and originality checks passed. |
| Alembic migration | `alembic upgrade head` against a disposable SQLite database passed. |
| Shell syntax | `bash -n` passed for every tracked shell script. |
| `make tools-check` | Go 1.27.4, Helm 3.10.1, kubectl 1.31.9/Kustomize 5.4.2, Kind 0.33.0, Docker CLI 27.3.1 and Python Sigstore/Kubernetes/Docker clients verified; Kustomize dev overlay rendered. |
| Release gates | `tools/verify_release.py --environment {dev,staging,prod} --allow-bootstrap` validated each non-deployable scaffold. Strict production mode rejected bootstrap. An isolated promotion dry run passed the strict staging/prod gates after `update_gitops.py`; `--allow-bootstrap` then correctly rejected the promoted state. |
| Generated manual | `make lab-manual` generated a 24-page PDF, an editable DOCX, Markdown source and 10 diagrams. The exact student metadata and absence of copied IPCV content were automatically checked. |

The configuration scan is also a gate: `tools/configure_platform.py --check`
rejects unset platform tokens and example-domain values in workspace text files,
and `tools/validate_repo.py` rejects those values in all three generated
lab-manual formats. The final combined release, lint, test, toolchain, syntax,
migration and configuration sweep printed `ALL FINAL CHECKS PASSED`.

## Application live preview

A local Uvicorn preview on `0.0.0.0:8000` was smoke-tested with GET requests to
`/`, `/healthz`, `/readyz`, `/metrics`, `/api/v1/info` and task CRUD. Security
headers, request IDs and trace IDs were present. The preview used a disposable
SQLite database in `.cache/` and was not a production deployment.

## Docker-independent runtime

`make local-runtime` builds from pinned `codeload.github.com` source archives;
`make local-runtime-check` verifies the generated binaries without contacting
the network. The following versions were observed in the sandbox:

| Binary | Observed result |
|---|---|
| Podman | `podman version 5.2.5` |
| conmon | `conmon version 2.1.12 / commit: local-source-build` |
| runc | `runc version unknown`, `spec: 1.0.2-dev`, `libseccomp: 2.5.5` |
| containerd / ctr | `containerd ... 1.7.20+unknown` |
| etcd | `etcd Version: 3.5.16` |
| Kubernetes | `Kubernetes v0.0.0-master+9edcffcde5595e8a5b1a35f88c421764e575afce` (source-tag build identity from Kubernetes v1.31.0) |

A final clean rebuild removed every generated runtime binary, library, header and
CNI plugin, then ran `make local-runtime` again from the pinned cached source
archives. Podman, conmon, libseccomp/runc, CNI plugins, containerd, Kubernetes
1.31.0 and etcd were rebuilt without a Go module proxy; `make local-runtime-check`
passed afterward.

A rootful Podman scratch image build and run printed:

```text
hello from rootful podman
```

That exact probe image was separately saved, imported into containerd and run
through kubelet in the local control plane.

## Local Kubernetes control plane

The source-built cluster is reproduced from a clean state by
`make local-cluster-up`; an earlier `/tmp` prototype informed the final script.
The verified control plane uses etcd, containerd, kube-apiserver,
controller-manager, scheduler and kubelet with kubeadm-generated certificates
and kubeconfigs. Exact observed results from the reproducible script:

| Check | Observed result |
|---|---|
| API readiness | `kubectl get --raw=/readyz` → `ok` |
| Node | `taskflow-local` → `Ready`, container runtime `containerd://1.7.20+unknown` |
| Component health | `etcd-0`, `controller-manager` and `scheduler` → `Healthy ok` |
| Pod scheduling | `taskflow-runtime-probe` → `Succeeded` (`Completed` in `kubectl get pods`), pod IP `10.244.0.36` |
| Container logs | `kubectl logs taskflow-runtime-probe` → `hello from rootful podman` |

`make local-cluster-check` codifies these checks against
`.cache/taskflow-local-cluster/`, including client-certificate verification of
`/readyz`, JSON inspection of Ready nodes and healthy component statuses, pod
phase/IP inspection and exact log matching. Final result:
`Local cluster validation passed: pinned binaries, supporting artifacts and live Kubernetes readiness.`

## Intentionally outside local validation

The following were **not** executed in this sandbox and are not claimed as
validated here:

- Docker daemon/Compose runtime, Kind-on-Docker, or the `make kind-up` workflow;
- native Terraform apply (the official release host is blocked);
- native Cosign binary verification (GitHub release asset hosts are blocked;
  the Python Sigstore client and pinned CI action are available);
- AWS provisioning, real EKS, RDS, S3, Route 53, ACM, IRSA or cloud backups;
- Argo CD and Argo Rollouts in-cluster behavior, Alertmanager delivery and
  Velero/RDS restore;
- live production CD/promotion workflow results and cloud deployments.

GitHub Actions PR CI checks are remote and are reported by `gh pr checks`; they
are not part of the sandbox-local checks above. The corresponding workflows,
manifests, policy gates, runbooks and release scripts are present and statically
validated locally. Production deployment workflows are intended for a real
runner, cluster or cloud account.
