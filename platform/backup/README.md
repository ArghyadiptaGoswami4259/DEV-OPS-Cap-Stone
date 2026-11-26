# Backup and recoverability

| State | Mechanism | Frequency | Retention | Recovery objective |
|---|---|---:|---:|---|
| Kubernetes desired state | Git repository and Argo CD | every commit | Git history | RPO 0 for declarative state |
| Cluster objects and volumes | Velero Schedule with CSI snapshots | daily 02:00 UTC | 30 days | RPO 24h, RTO under 30 min |
| PostgreSQL data | RDS automated backups plus RDS snapshot CronJob | continuous + daily | 7-30 days by environment | RPO under 5 min with PITR |
| Container artifacts | Immutable GHCR digests, SBOM and signature | every CI run | repository lifecycle policy | exact rebuild from Git SHA |
| Terraform state | Versioned S3 + DynamoDB locking | every apply | S3 versioning | rollback to prior state version |

`runbooks/dr-restore.md` gives the restore order. Never restore a database snapshot over a newer
schema without checking the Alembic revision; application and schema changes must be rolled back
together. Drill the restore quarterly and record the measured RTO.
