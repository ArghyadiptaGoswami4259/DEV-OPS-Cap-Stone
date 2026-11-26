output "cluster_name" {
  description = "EKS cluster name for kubeconfig generation."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded cluster certificate authority."
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "configure_kubectl" {
  description = "Command that adds the environment cluster to kubeconfig."
  value       = "aws eks --region ${var.region} update-kubeconfig --name ${module.eks.cluster_name}"
}

output "vpc_id" {
  description = "VPC identifier."
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet identifiers used by EKS and RDS."
  value       = module.vpc.private_subnets
}

output "ecr_repository_url" {
  description = "Immutable ECR repository for TaskFlow images."
  value       = aws_ecr_repository.taskflow.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint."
  value       = aws_db_instance.taskflow.endpoint
  sensitive   = true
}

output "rds_master_secret_arn" {
  description = "Secrets Manager ARN holding generated PostgreSQL credentials."
  value       = aws_db_instance.taskflow.master_user_secret_arn
  sensitive   = true
}

output "backup_bucket_name" {
  description = "Versioned, encrypted S3 bucket for Velero and backup metadata."
  value       = aws_s3_bucket.backups.bucket
}

output "external_secrets_role_arn" {
  description = "IRSA role ARN for the External Secrets service account."
  value       = aws_iam_role.external_secrets.arn
}

output "backup_role_arn" {
  description = "IRSA role ARN for Velero and the RDS snapshot CronJob."
  value       = aws_iam_role.backup.arn
}

output "oidc_provider_arn" {
  description = "EKS OIDC provider ARN for additional IRSA bindings."
  value       = module.eks.oidc_provider_arn
}
