# Setup and reproduction guide

## Prerequisites

- Python 3.11+, Git, Docker and Docker Compose for the local application.
- `kind`, `kubectl`, `helm` and `openssl` for the local Kubernetes platform.
- Terraform 1.9+, AWS CLI and configured AWS credentials for the optional AWS platform.

## Fast path (no cloud account)

```bash
make install
make test
make validate
make run                 # http://localhost:8000
```

For PostgreSQL, Prometheus, Loki and Grafana:

```bash
make env
make compose-observability
# TaskFlow http://localhost:8000, Grafana http://localhost:3000
```

For the full local Kubernetes platform:

```bash
make kind-up              # builds the image, installs pinned charts, applies dev overlay
make verify-platform
make canary-drill
```

`make kind-up` requires a working Docker daemon. `WITH_GITOPS=true make kind-up` also installs Argo
CD and applies the app-of-apps ApplicationSet. `WITH_VELERO=true make kind-up` installs Velero,
but only after replacing the AWS bucket and role placeholders in `platform/backup/velero-values.yaml`.

## AWS path

1. Bootstrap remote state:

```bash
terraform -chdir=infra/terraform/bootstrap init
terraform -chdir=infra/terraform/bootstrap apply
```

2. Copy `state_bucket` and `lock_table` outputs into each
   `infra/terraform/environments/<env>.backend.hcl`.
3. Initialize and review an environment:

```bash
bash infra/scripts/terraform-init.sh prod
terraform -chdir=infra/terraform plan -var-file=environments/prod.tfvars
terraform -chdir=infra/terraform apply -var-file=environments/prod.tfvars
```

4. Replace `REPLACE_WITH_*` values in the staging/prod overlays and platform Helm values with
   Terraform outputs, real DNS names, notification email and approved certificate issuers.
5. Configure GitHub Environment protection rules: require reviewers for `production`, restrict
   deployment branches and record the approver identity.
6. Install the platform Helm charts, then apply `platform/argocd/project.yaml` and
   `applicationset.yaml`. The production Application remains intentionally unhealthy until the
   first signed promotion: the bootstrap zero digest is unsigned and Kyverno blocks its pods.

Never commit a real database URL, AWS key, certificate private key or webhook URL. Production
credentials are read from AWS Secrets Manager through External Secrets with IRSA.
