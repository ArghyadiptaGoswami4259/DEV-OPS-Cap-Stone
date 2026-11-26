# Disaster recovery and restore

## Scope

- RPO: up to 60 minutes (RDS automated backups/PITR support a much smaller real-world RPO).
- RTO: 30 minutes for a single-region cluster restore.
- Source of truth: this Git repository for desired state, GHCR/ECR for signed images, Terraform
  state for infrastructure, Velero for cluster objects/volumes, and RDS snapshots for data.

## Restore order

1. Confirm the incident and freeze production promotions.
2. Restore infrastructure from the reviewed Terraform state/version if the cluster is unavailable.
3. Update kubeconfig and install pinned platform charts using the approved chart bundle.
4. Apply Argo CD bootstrap and wait for the app-of-apps ApplicationSet to become healthy.
5. List backups: `bash infra/scripts/backup-restore.sh --list`.
6. Restore cluster resources: `bash infra/scripts/backup-restore.sh --backup <name> --confirm`.
7. Restore RDS to a PITR point or snapshot that matches the Alembic revision of the desired image.
8. Validate secret references, DNS, certificates, Ingress and NetworkPolicies.
9. Run `make verify-platform`, canary smoke tests and a synthetic CRUD test.
10. Record the measured RTO, data-loss window and corrective actions.

Do not restore a database snapshot newer than the application's expected schema without a reviewed
migration plan. Keep at least one restore drill evidence set per academic term or quarter.
