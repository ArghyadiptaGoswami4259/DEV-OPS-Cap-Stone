# Security policy

## Reporting a vulnerability

Report vulnerabilities privately through the repository's GitHub Security Advisories feature.
Do not open a public issue for an exploitable defect. Include the affected digest, environment,
reproduction steps, impact and any suggested remediation.

## Built-in controls

- Branch protection, CODEOWNERS, required reviews and conventional commit checks.
- Pinned GitHub Actions, least-privilege workflow permissions and concurrency limits.
- CodeQL, Bandit, Gitleaks, Trivy filesystem/IaC/image scans, `pip-audit` and Dependabot.
- Keyless Cosign signatures, Buildx provenance and SPDX SBOMs for immutable images.
- Non-root, read-only containers with dropped capabilities, seccomp and resource limits.
- Kyverno admission policies, Pod Security `restricted`, NetworkPolicies and IRSA.
- External Secrets for database credentials; no production secret values in Git.
- TLS, rate limiting, security headers, WAF annotations and strict input validation.

## Incident handling

Follow `runbooks/incident-response.md`, then `runbooks/rollback.md`. Preserve logs, image
digests, Git SHAs and rollout revisions as evidence. Rotate credentials if exposure is suspected.
