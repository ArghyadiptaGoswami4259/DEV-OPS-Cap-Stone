# Version-control strategy

- `main` is the protected delivery branch; short-lived `feat/*`, `fix/*`, `chore/*` and `docs/*`
  branches are merged by reviewed pull requests.
- Commit subjects follow Conventional Commits and are checked by the `commit-msg` hook.
- CODEOWNERS requires review of workflows, application, infrastructure, deployment and security
  changes.
- Pull requests require CI, CodeQL, secret scanning, image scanning, tests and no new high/critical
  findings.
- Releases are represented by immutable image digests and GitHub release tags, never by a mutable
  `latest` tag.
- GitOps promotion commits use `[skip ci]` and are ignored by CI path filters to prevent loops.
- `staging` promotion is automatic after signed CI; `production` requires a protected GitHub
  Environment approval and a strict release gate.

Run `make hooks` to install the local commit-message and pre-commit checks.
