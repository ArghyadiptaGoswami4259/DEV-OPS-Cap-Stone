# Setup and reproduction guide

## Prerequisites

- Python 3.11+, Git, Docker and Docker Compose for the local application.
- `kind`, `kubectl`, `helm` and `openssl` for the local Kubernetes platform.
- Terraform 1.9+, AWS CLI and configured AWS credentials for the optional AWS platform.

## Fast path (no cloud account)

```bash
make install
make tools
make configure           # optional: render overrides from config/platform.env
make configure-check
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

For the full local Kubernetes platform on a machine with Docker:

```bash
make kind-up              # builds the image, installs pinned charts, applies dev overlay
make verify-platform
make canary-drill
```

`make kind-up` requires a working Docker daemon. `WITH_GITOPS=true make kind-up` also installs Argo
CD and applies the app-of-apps ApplicationSet. `WITH_VELERO=true make kind-up` installs Velero,
but only after setting real AWS bucket and role values with `make configure`.

For a Docker-daemon-free control plane and pod-runtime validation:

```bash
make local-runtime        # build Podman/containerd/runc/CNI/etcd/Kubernetes from source
make local-cluster-up     # start local etcd, API server, controllers, scheduler and kubelet
make local-cluster-check  # verify readiness, node health, Pod scheduling and container logs
make local-cluster-down   # stop the local control plane
```

This path uses rootful Podman, containerd and runc locally; see `docs/local-runtime.md`. It is a
reproducible validation cluster, not a production Kubernetes distribution.

## AWS path

1. Bootstrap remote state:

```bash
terraform -chdir=infra/terraform/bootstrap init
terraform -chdir=infra/terraform/bootstrap apply
```

2. Set `TASKFLOW_TF_STATE_PREFIX` and `TASKFLOW_TF_LOCK_TABLE` from the bootstrap outputs in
   `config/platform.env` (or export them), then run `make configure`. The three environment backend
   HCL files are rendered deterministically from those two values.
3. Initialize and review an environment:

```bash
bash infra/scripts/terraform-init.sh prod
terraform -chdir=infra/terraform plan -var-file=environments/prod.tfvars
terraform -chdir=infra/terraform apply -var-file=environments/prod.tfvars
```

4. Set real DNS, certificate email, RDS and IRSA role values in `config/platform.env` (or export
   matching environment variables), then run `make configure` and `make configure-check`. The
   staging/prod overlays, backup policy, certificate issuers and observability examples are
   rendered from that single input set.
5. Configure GitHub Environment protection rules: require reviewers for `production`, restrict
   deployment branches and record the approver identity.
6. Install the platform Helm charts, then apply `platform/argocd/project.yaml` and
   `applicationset.yaml`. The production Application remains intentionally unhealthy until the
   first signed promotion: the bootstrap zero digest is unsigned and Kyverno blocks its pods.

Never commit a real database URL, AWS key, certificate private key or webhook URL. Production
credentials are read from AWS Secrets Manager through External Secrets with IRSA.
