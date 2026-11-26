# Pipeline failure triage

| Failed stage | First checks | Safe remediation |
|---|---|---|
| Lint/type/test | local `make lint`, `make test` | fix code, add regression test, do not bypass |
| CodeQL/Bandit/Semgrep | SARIF annotation and affected rule | patch insecure pattern or document a reviewed exception |
| Gitleaks | suspected file and entropy pattern | rotate credential, remove from history, never add allowlist for a real secret |
| Trivy | CVE or misconfiguration ID | upgrade pinned dependency/base image or apply the missing control |
| pip-audit | advisory ID and fixed version | update pinned requirement and rerun tests |
| Build/push | Buildx log, GHCR permissions, disk | verify `packages: write` and immutable tag |
| Cosign | OIDC token, issuer, workflow identity | confirm `id-token: write` and exact CI workflow reference |
| CD signature verification | digest artifact, GHCR login, certificate identity | rerun CI rather than promoting unsigned image |
| Argo CD sync | `argocd app diff`, hook Job logs, CRD versions | fix manifest or migration; never disable self-heal permanently |
| Canary analysis | AnalysisRun result, Prometheus queries, trace IDs | abort, restore last good digest, add detection test |
