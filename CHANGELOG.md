# Changelog

All notable changes to the DevOps automation platform are documented here. The format is based on
Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Quick links in `README.md` for the repository, full capstone PDF, screenshots-only PDF,
  interactive evidence gallery and local preview ports.
- A clickable GitHub repository link on the lab manual cover and matching repository links in the
  DOCX and Markdown deliverables.
- Appendix C with 14 local-host implementation screenshots, a standalone screenshots-only PDF,
  an interactive evidence gallery, structured evidence JSON and reproducible capture slides.
- `make evidence-install`, `make evidence` and `make evidence-showcase` for headless-browser
  screenshot capture and a local `0.0.0.0:8011` showcase server.
- `config/platform.env` plus `make configure` / `make configure-check` for deterministic,
  self-configuring Terraform backends, GitOps overlays, backup ARNs, DNS names, certificate email
  and observability values.
- `make local-runtime`, `make local-runtime-check`, `make local-cluster-up`,
  `make local-cluster-check` and `make local-cluster-down`: a reproducible Docker-daemon-independent
  Podman/conmon/libseccomp/runc/CNI/containerd/etcd/Kubernetes runtime and local control plane.
- `docs/local-runtime.md` and `docs/validation-evidence.md` documenting the source-built runtime and
  exact local verification results.

### Changed
- Install pinned Trivy 0.76.2 from its SHA256-verified release asset for both filesystem and image
  scans so PR CI does not depend on the unavailable `get.trivy.dev` installer endpoint.
- Retry transient GitHub release-asset HTTP failures with bounded timeouts and a pinned digest.
- Keep Trivy's SARIF output aligned with the configured CRITICAL/HIGH gate so medium and low
  findings do not incorrectly fail the CI job.
- Add a dated, path-scoped Trivy exception for an unrestricted egress rule inside the upstream
  EKS Terraform module; repository-managed security groups remain restricted.
- Validate GHCR repositories by parsed hostname in the release gate and remove an invalid
  `pip --require-hashes=false` flag from the container build.
- Resolve CodeQL import and empty-exception advisories in the application and runtime checker.
- Align PyYAML 6.0.3 with the Kubernetes client so `make install` resolves development and
  optional platform-tool dependencies together.
- Harden Terraform state and backup buckets with customer-managed KMS keys, restrict database
  egress to EKS nodes, and make the development PostgreSQL container use a read-only root
  filesystem with writable ephemeral directories.
- Generate the local kubeadm bootstrap token at runtime so the CI secret scanner sees no static
  credential-like value.
- Removed unset configuration tokens and example domains from tracked manifests, workflows, docs and
  generated lab-manual formats; a repository gate now rejects their reintroduction.
- Updated setup, toolchain, production-readiness and verification documentation to distinguish the
  validated local Kubernetes path from cloud/in-cluster operations that still require a real runner.

## [1.0.0] - 2026-11-26

### Added
- TaskFlow FastAPI application with health, readiness, Prometheus metrics, structured JSON logs,
  W3C trace context, strict schemas and PostgreSQL/Alembic persistence.
- Unit/API tests, Ruff, MyPy, `pip-audit`, repository manifest validation and Git hooks.
- Multi-stage hardened Dockerfile and reproducible local Compose stack.
- Pinned GitHub Actions CI with CodeQL, Gitleaks, Trivy, SBOM, Buildx provenance and Cosign signing.
- Terraform AWS platform, Kind bootstrap, GitOps overlays, Argo CD and Argo Rollouts canary analysis.
- Prometheus/Grafana/Loki observability, SLO alerts, canary analysis and dashboard provisioning.
- Kyverno policies, NetworkPolicies, External Secrets, IRSA and threat model.
- Velero/RDS backup policy, rollback and disaster-recovery runbooks.
- Lab manual in the supplied visual template with original DevOps content and student details.
- `make tools` local toolchain installer and `make tools-check` verifier using sandbox-allowlisted
  sources for Go, Helm, kubectl/Kustomize, Kind, Docker CLI and Python platform clients.

### Changed
- Upgraded FastAPI/Starlette to audited versions after `pip-audit` identified vulnerabilities in the
  previous pinned Starlette release; the test client now uses `httpx2`.
- Made Kyverno image-signature enforcement active by default and marked bootstrap release manifests
  as explicitly non-deployable scaffolding.
