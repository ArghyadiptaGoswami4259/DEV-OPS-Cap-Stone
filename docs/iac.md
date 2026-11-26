# Infrastructure as Code

Terraform provisions an environment-specific AWS platform:

- a three-AZ VPC with public/private subnets, DNS and NAT (one NAT for non-production, one per AZ
  for production);
- an EKS cluster with private worker subnets, control-plane logs, managed node groups and IRSA;
- an immutable, encrypted, scan-on-push ECR repository;
- encrypted PostgreSQL with generated credentials in Secrets Manager, KMS, private access,
  Multi-AZ in production, automated backups and CloudWatch log export;
- a versioned, encrypted, TLS-only S3 backup bucket with lifecycle expiration;
- separate least-privilege IRSA roles for External Secrets and backup operations.

Remote state is an S3 bucket with versioning and a DynamoDB lock table. Provider and module
versions are pinned; tfvars are separated for dev, staging and prod. State files, `.terraform`,
`.env` and local databases are ignored by Git.

Local clusters use `infra/kind-config.yaml` and pinned chart versions in `platform/versions.env`,
so the lab reproduction does not require a cloud bill.
