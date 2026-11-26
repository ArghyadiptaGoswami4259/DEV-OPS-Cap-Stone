environment              = "staging"
region                   = "ap-south-1"
vpc_cidr                 = "10.43.0.0/16"
kubernetes_version       = "1.31"
node_instance_type       = "t3.medium"
node_min_size            = 2
node_desired_size        = 3
node_max_size            = 5
db_instance_class        = "db.t3.small"
db_allocated_storage     = 30
db_max_allocated_storage = 100
db_backup_retention_days = 14
tags = {
  CostCentre = "lab"
  DataClass  = "non-production"
}
