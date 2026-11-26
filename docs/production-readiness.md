# Production-readiness checklist

## Automated gates

- [x] Unit/API tests and branch coverage
- [x] Ruff, MyPy, Bandit, HCL/Kustomize/repository validation
- [x] `pip-audit` reports no known vulnerabilities in pinned runtime requirements
- [x] CodeQL, Bandit, Gitleaks, Trivy filesystem/IaC/image scans, pip-audit
- [x] Pinned GitHub Actions, least-privilege workflow permissions
- [x] Immutable digest, SPDX SBOM, Buildx provenance, keyless Cosign signature
- [x] Strict production release gate (`tools/verify_release.py --environment prod`)
- [x] Signed-artifact verification in staging and production promotion
- [x] Canary analysis and automatic rollback policy
- [x] Prometheus alerts, Grafana dashboard, Loki rules and structured logs
- [x] Velero/RDS backup policy and DR runbook
- [x] Non-root Pod Security, NetworkPolicy, Kyverno and External Secrets manifests

## Operator actions before first production promotion

- [x] Platform values are generated from the checked-in `config/platform.env`; `make configure-check`
      verifies every backend, overlay, backup, certificate, DNS and log-query value is synchronized.
- [ ] Override the safe local defaults with the approved AWS account ID, Terraform outputs, DNS names,
      certificate email and IRSA role ARNs before a cloud deployment, then run `make configure`.
- [ ] Configure branch protection, CODEOWNERS enforcement and the `production` Environment
      reviewers.
- [ ] Replace example webhook, Grafana and Alertmanager destinations with approved endpoints.
- [ ] Verify real OCI image digests for third-party images and pin them in production overlays.
- [x] Kyverno image-signature policy is `Enforce` by default; bootstrap pods are blocked until a signed promotion.
- [ ] Run `terraform plan`, apply in a non-production account, and validate cost/alarm settings.
- [ ] Perform a restore drill and record the measured RPO/RTO.
- [ ] Run the canary drill in staging and attach the AnalysisRun evidence to the release record.
- [ ] Load-test the chosen node class and tune HPA, resource requests and ingress rate limits.

The three checked-in `release.yaml` files are annotated `taskflow.devops/state: bootstrap`. They
are non-deployable scaffolding that records the policy shape before the first build; they are
deliberately rejected by `tools/verify_release.py --environment prod` and by Kyverno signature
enforcement. `tools/update_gitops.py` changes the annotation to `promoted` only after writing a
signed digest, source commit, approval and immutable promotion timestamp.

This repository is a complete, reproducible blueprint and a runnable local implementation.
Cloud resources are intentionally declarative and are not provisioned by the repository itself.
