variable "project" {
  description = "Short project name used in resource names and tags."
  type        = string
  default     = "taskflow"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "region" {
  description = "AWS region for the platform."
  type        = string
  default     = "ap-south-1"
}

variable "owner" {
  description = "Owner tag applied to reproducible infrastructure."
  type        = string
  default     = "Arghyadipta Goswami"
}

variable "vpc_cidr" {
  description = "RFC1918 CIDR block for the environment VPC."
  type        = string
  default     = "10.42.0.0/16"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 1))
    error_message = "vpc_cidr must be a valid CIDR block."
  }
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "Instance type for managed worker nodes."
  type        = string
  default     = "t3.medium"
}

variable "node_min_size" {
  description = "Minimum managed node count."
  type        = number
  default     = 2
  validation {
    condition     = var.node_min_size >= 1
    error_message = "node_min_size must be at least one."
  }
}

variable "node_desired_size" {
  description = "Desired managed node count."
  type        = number
  default     = 3
}

variable "node_max_size" {
  description = "Maximum managed node count."
  type        = number
  default     = 6
}

variable "db_instance_class" {
  description = "RDS PostgreSQL instance class."
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Initial RDS storage in GiB."
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum storage for RDS autoscaling in GiB."
  type        = number
  default     = 100
}

variable "db_backup_retention_days" {
  description = "RDS automated backup retention in days."
  type        = number
  default     = 14
  validation {
    condition     = var.db_backup_retention_days >= 7 && var.db_backup_retention_days <= 35
    error_message = "db_backup_retention_days must be between 7 and 35."
  }
}

variable "tags" {
  description = "Additional tags merged into the platform tags."
  type        = map(string)
  default     = {}
}
