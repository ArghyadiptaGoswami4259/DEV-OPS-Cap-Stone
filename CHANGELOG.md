# Changelog

All notable changes to the DevOps automation platform are documented here. The format is based on
Keep a Changelog, and this project follows Semantic Versioning.

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

### Changed
- Upgraded FastAPI/Starlette to audited versions after `pip-audit` identified vulnerabilities in the
  previous pinned Starlette release; the test client now uses `httpx2`.
- Made Kyverno image-signature enforcement active by default and marked bootstrap release manifests
  as explicitly non-deployable scaffolding.
