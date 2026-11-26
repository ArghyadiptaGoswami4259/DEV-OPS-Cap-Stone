environment              = "prod"
region                   = "ap-south-1"
vpc_cidr                 = "10.44.0.0/16"
kubernetes_version       = "1.31"
node_instance_type       = "m6i.large"
node_min_size            = 3
node_desired_size        = 4
node_max_size            = 8
db_instance_class        = "db.m6g.large"
db_allocated_storage     = 100
db_max_allocated_storage = 500
db_backup_retention_days = 30
tags = {
  CostCentre = "capstone-production"
  DataClass  = "production"
}
