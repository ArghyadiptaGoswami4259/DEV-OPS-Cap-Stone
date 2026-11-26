# Contributing to TaskFlow

## Version-control workflow

1. Create a short-lived branch from the active delivery branch.
2. Use a [Conventional Commit](https://www.conventionalcommits.org/) subject, for example
   `feat(api): add filtering` or `fix(rollout): tighten readiness probe`.
3. Open a pull request using the template. Keep the diff focused and include evidence.
4. Required checks are CI, CodeQL, Gitleaks, Trivy, tests, type checks and repository validation.
5. Squash-merge after review. Never push directly to a protected production branch.

## Local setup

```bash
make install
make hooks
make test
make validate
make run
```

## Definition of done

- Tests and type checks pass, with no new high/critical scanner findings.
- Configuration is declarative and environment-neutral; secrets stay in Secret Manager.
- New endpoints expose metrics and structured log context.
- Kubernetes changes include probes, resource limits, a security context and rollback notes.
- The lab manual is regenerated with `make lab-manual` when an experiment changes.

## Release flow

A successful CI run publishes a signed image digest. CD verifies the signature, updates the
staging overlay and commits the immutable digest. Production promotion is a separately approved
`CD - production approval and canary promotion` workflow. Argo CD reconciles Git state and Argo
Rollouts performs metric-based canary analysis with automatic abort.
