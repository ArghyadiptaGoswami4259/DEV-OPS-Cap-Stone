# TaskFlow: end-to-end DevOps automation platform

**Capstone submission:** Arghyadipta Goswami | Roll 2301010192 | B.Tech CSE Section C |
Year 2023-2027 | Subject: Dev Ops and Automation

TaskFlow is a small FastAPI task application used as the workload for a complete, reproducible
commit-to-production platform. A code commit triggers quality and security gates, an immutable
and signed OCI image, GitOps promotion, Kubernetes orchestration, metric-driven canary delivery,
observability and recoverability. The same repository contains the generated academic lab manual.

> The attached IPCV PDF was used **only** as a visual template for the lab manual. All technical
> content, experiments, code, diagrams and outputs in this repository are original.

## What is included

| Area | Delivered |
|---|---|
| Application | FastAPI UI/API, PostgreSQL + Alembic, strict schemas, health/readiness, custom Prometheus metrics, JSON logs, W3C request correlation |
| Version control | Conventional Commits, CODEOWNERS, PR/issue templates, Git hooks, branch strategy, Dependabot, release tags |
| CI/CD | Pinned GitHub Actions, tests, Ruff, MyPy, CodeQL, Bandit, Gitleaks, Trivy, pip-audit, SBOM, Buildx provenance, Cosign, staging auto-promotion, protected production promotion |
| Containerization | Hardened multi-stage Dockerfile, `.dockerignore`, local Compose app/database and optional Prometheus/Loki/Promtail/Grafana profile |
| Infrastructure | Terraform AWS VPC/EKS/ECR/RDS/S3/KMS/IRSA plus S3 remote state bootstrap; Kind config and pinned chart bootstrap for local reproduction |
| Kubernetes | Kustomize base and dev/staging/prod overlays, Argo CD ApplicationSet, Argo Rollouts canary, migration Job, ingress/TLS/WAF annotations, HPA, PDB, NetworkPolicy, probes, security contexts |
| Observability | ServiceMonitor, PrometheusRule alerts, Grafana dashboard, Alertmanager routing, structured Loki logs, LogQL queries, canary AnalysisTemplate |
| Security | Least-privilege workflow permissions, signed images, Kyverno policies, restricted Pod Security, secret scanning, External Secrets, IRSA, no production secrets in Git |
| Recovery | Automatic canary abort, explicit rollback, Velero/RDS backups, versioned Terraform state, rollback/incident/DR runbooks |
| Academics | A styled PDF, editable DOCX and Markdown lab manual with the requested student details |

## Repository map

```text
app/                     TaskFlow API, UI, config, database, logging, metrics, middleware
tests/                   Pytest API, validation, metrics, canary and security-posture tests
.github/workflows/        CI, staging CD and approved production promotion
infra/terraform/          AWS modules, tfvars, backend bootstrap, outputs
infra/scripts/            Kind bootstrap, Terraform init, verification, canary drill, rollback, restore
deploy/gitops/            Kustomize base, Argo Rollout, analysis, services, policies, env overlays
platform/argocd/          AppProject, ApplicationSet, values
platform/observability/   Prometheus, Alertmanager, Loki, Promtail, Grafana dashboard and rules
platform/security/        Kyverno, cert-manager, Gitleaks, Trivy, Semgrep, RBAC
platform/backup/          Velero values/schedule, RDS snapshots, backup policy
docs/                     Architecture, pipeline, SLO, threat model, setup, canary, observability
runbooks/                 Rollback, incident response, disaster recovery, pipeline triage
tools/                    Manifest validation, GitOps promotion, release gate, lab-manual generator
docs/lab-manual/          Generated PDF, DOCX, Markdown and design assets
```

## Quick start

```bash
make install       # virtualenv + pinned dependencies + random local .env
make tools         # local Go/Helm/kubectl/Kind/Docker CLI into ignored .tools/
make tools-check   # verify the local platform toolchain
make test          # API and platform behaviour tests
make lint          # Ruff, MyPy, YAML/JSON, pinned actions, secret heuristics, pip-audit
make validate      # manifest/structure validation
make run           # http://localhost:8000 with disposable SQLite
```

Full local stack:

```bash
make compose-observability
# TaskFlow http://localhost:8000 | Grafana http://localhost:3000
make kind-up
make verify-platform
make canary-drill
```

`make tools` installs Go, Helm, kubectl/Kustomize, Kind and the Docker CLI from sandbox-allowlisted
sources; see [`docs/toolchain.md`](docs/toolchain.md). Put `.tools/bin` on `PATH` before running
cluster commands. `make kind-up` additionally requires a working Docker daemon or compatible
container runtime; the sandbox provides the client but not the daemon. In a normal runner it creates
a four-node cluster, installs pinned versions of Prometheus Operator/Grafana, ingress-nginx,
cert-manager, External Secrets, Argo Rollouts, Loki/Promtail and Kyverno, builds/loads
`taskflow:local`, and applies the dev overlay. Argo CD and Velero are opt-in with
`WITH_GITOPS=true` and `WITH_VELERO=true`.

## Delivery flow

```text
commit -> PR checks -> signed immutable digest -> staging GitOps commit -> Argo CD
       -> Alembic PreSync -> 20% canary -> Prometheus analysis -> 50% -> analysis -> 100%
       -> approved production promotion -> production canary -> automatic abort on SLO breach
```

Production promotion is a manual `workflow_dispatch` in a protected GitHub Environment. It
verifies the Cosign signature and workflow identity, updates the production digest, enforces
`tools/verify_release.py`, commits the GitOps state and tags the release. See
`docs/pipeline.md` and `docs/canary.md`.

## Production deployment notes

Cloud infrastructure is declarative; it is **not** provisioned by cloning this repository. Review
`docs/setup.md`, set real account/DNS overrides in `config/platform.env` (or environment
variables), run `make configure`, apply the Terraform bootstrap, configure branch protection and
the `production` Environment reviewers, then apply the Argo CD bootstrap. The checked-in `release.yaml` files are explicitly annotated
`taskflow.devops/state: bootstrap`: they are non-deployable scaffolding, not promoted releases.
Only `tools/update_gitops.py` can mark a signed digest as promoted, and the strict release gate
rejects the bootstrap state. Third-party image tags used for the local lab should be pinned to
verified digests for a real production account. The production-readiness checklist is in
`docs/production-readiness.md`.

## Lab manual

- Primary: [`docs/lab-manual/DevOps-and-Automation-Lab-Manual.pdf`](docs/lab-manual/DevOps-and-Automation-Lab-Manual.pdf)
- Editable: [`docs/lab-manual/DevOps-and-Automation-Lab-Manual.docx`](docs/lab-manual/DevOps-and-Automation-Lab-Manual.docx)
- Source: [`docs/lab-manual/DevOps-and-Automation-Lab-Manual.md`](docs/lab-manual/DevOps-and-Automation-Lab-Manual.md)

Regenerate with `make lab-manual`. The generator uses the supplied template's colours, cover,
header/footer, headings, code-panel and output-table design, but contains no IPCV content.

## Verification status

- `make lint`: Ruff, MyPy, Bandit, repository validation and `pip-audit` passed; no known runtime
  vulnerabilities in the pinned requirements.
- `make test`: 11 passed.
- `make tools` / `make tools-check`: installed and verified Go 1.27.4, Helm 3.10.1, kubectl
  1.31.9/Kustomize v5.4.2, Kind 0.33.0, Docker CLI 27.3.1 and the Python Sigstore/Kubernetes/Docker
  clients; binaries are kept in ignored `.tools/` rather than committed.
- `make configure-check` / `make validate`: required files, synchronized platform configuration,
  Python/shell, YAML/JSON/HCL, Kustomize references, pinned actions, secret heuristics, lab-manual
  student details and originality checks passed.
- `alembic upgrade head` against a disposable SQLite database and `bash -n` for every shell script:
  passed.
- `make local-runtime` / `make local-runtime-check`: a clean rebuild and verification of Podman
  5.2.5, conmon 2.1.12, runc v1.1.14 with libseccomp 2.5.5, CNI plugins v1.5.1, containerd 1.7.20,
  etcd 3.5.16 and the Kubernetes 1.31.0 control-plane binaries from allowlisted source archives;
  binaries remain in ignored `.tools/` rather than committed.
- `make local-cluster-up` / `make local-cluster-check`: validated `/readyz`, one Ready node, healthy
  etcd/scheduler/controller-manager components, a scheduled Pod with an assigned pod IP, and
  container logs without using the Docker daemon.
- `tools/verify_release.py --allow-bootstrap`: validates dev/staging/prod as non-deployable
  scaffolds; the strict production gate rejects them until a signed promotion.
- Isolated promotion dry run: `update_gitops.py` followed by the strict staging/prod release gates
  passed; `--allow-bootstrap` then correctly rejected the promoted state.
- Live preview: `/`, `/healthz`, `/readyz`, `/api/v1/info`, task CRUD, `/metrics`, security headers
  and trace IDs were smoke-tested.
- Lab manual: 24-page PDF, editable DOCX and Markdown source generated with `make lab-manual`;
  exact student details and absence of copied IPCV content are automatically checked.

Still not executed end-to-end: Docker **daemon**/Compose and Kind-on-Docker paths, native
Terraform apply, native Cosign verification, real AWS provisioning, Argo CD/Rollouts in-cluster
behavior, Alertmanager delivery, Velero/RDS restore and production CD/promotion workflows.
GitHub Actions PR CI checks run remotely and are reported by `gh pr checks`. The
Docker-independent local Kubernetes path is validated through
`make local-runtime`, `make local-cluster-up` and `make local-cluster-check`; see
`docs/local-runtime.md` and `docs/validation-evidence.md`. The official Terraform and Cosign binary
hosts remain blocked by the sandbox allowlist. Cloud manifests and production deployment workflows
are intended for a real runner or cluster.

## License and ownership

MIT License. Copyright 2026 Arghyadipta Goswami. See `LICENSE` and `CONTRIBUTING.md`.
