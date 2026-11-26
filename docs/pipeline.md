# Commit-to-production pipeline

| Stage | Trigger | Checks | Artifact / state change |
|---|---|---|---|
| 1. Local guard | `pre-commit`, `commit-msg` | Conventional Commit, Ruff, pytest, YAML/JSON parse | clean commit |
| 2. Pull request | `CI` on PR | Ruff, MyPy, pytest + coverage, Bandit, pip-audit, CodeQL, Gitleaks, Trivy filesystem/IaC | review evidence |
| 3. Image build | `CI` on push | Buildx, SBOM, provenance, Trivy image scan | image digest in GHCR |
| 4. Supply chain | `CI` on push | Cosign keyless signature, SPDX SBOM artifact | signed immutable digest |
| 5. Staging CD | successful `CI` workflow run | digest format, Cosign issuer/workflow verification, release gate | staging GitOps commit `[skip ci]` |
| 6. GitOps sync | Argo CD | Kustomize render, PreSync Alembic migration | dev/staging Rollout |
| 7. Canary | Rollout revision | 20% -> analysis -> 50% -> analysis -> 100% | Healthy or Degraded |
| 8. Production approval | manual `promote.yml` | GitHub Environment reviewers, Cosign, strict release gate | prod GitOps commit + release tag |
| 9. Production canary | Argo CD/Rollouts | error rate < 2%, p95 < 500 ms, readiness | automatic abort on breach |
| 10. Steady state | continuous | Prometheus alerts, Loki logs, backups, dashboards | observable recoverable service |

The CI workflow ignores `deploy/gitops/**`, generated lab-manual binaries and Markdown-only changes,
so GitOps promotion commits cannot create an infinite pipeline. Workflow permissions are
least-privilege, all third-party actions are pinned to full commit SHAs, and production promotion
is isolated in a protected GitHub Environment.
