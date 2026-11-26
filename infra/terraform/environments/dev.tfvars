environment              = "dev"
region                   = "ap-south-1"
vpc_cidr                 = "10.42.0.0/16"
kubernetes_version       = "1.31"
node_instance_type       = "t3.small"
node_min_size            = 2
node_desired_size        = 2
node_max_size            = 4
db_instance_class        = "db.t3.micro"
db_allocated_storage     = 20
db_max_allocated_storage = 50
db_backup_retention_days = 7
tags = {
  CostCentre = "lab"
  DataClass  = "non-production"
}
