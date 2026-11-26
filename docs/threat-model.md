# Threat model (STRIDE)

| Threat | Example | Control | Residual action |
|---|---|---|---|
| Spoofing | forged CI identity or unsigned image | OIDC keyless Cosign, certificate issuer/workflow checks, Kyverno image verification, GitHub Environment approval | enable Kyverno Enforce after first signed rollout |
| Tampering | altered source, dependency, image or GitOps digest | branch protection/CODEOWNERS, immutable ECR/GHCR digests, SBOM, provenance, signed commits where available, Argo CD self-heal | review supply-chain exceptions |
| Repudiation | unclear production approval | protected GitHub Environment, release tags, `[skip ci]` promotion commit, Terraform state history, audit logs | retain logs and release evidence |
| Information disclosure | leaked credentials or verbose errors | Gitleaks, External Secrets + IRSA, KMS, no secrets in env files, generic 500 responses, TLS-only S3 policy | rotate on suspected exposure |
| Denial of service | traffic spike or crash-loop | ingress rate limits, HPA, PDB, resource limits, probes, NetworkPolicy, canary rollback | load-test and tune thresholds |
| Elevation of privilege | privileged container or broad IAM | restricted Pod Security, non-root/read-only/cap-drop, least-privilege IRSA, workflow permissions | quarterly policy review |

Additional security controls: CodeQL, Bandit, Trivy filesystem/IaC/image scans, `pip-audit`,
Dependabot, Semgrep rules, CSP/security headers, strict Pydantic schemas, OWASP ModSecurity
annotations, and Kubernetes NetworkPolicies.
