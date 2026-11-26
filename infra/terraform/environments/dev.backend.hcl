bucket         = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
key            = "taskflow/dev/terraform.tfstate"
region         = "ap-south-1"
dynamodb_table = "REPLACE_WITH_TERRAFORM_LOCK_TABLE"
encrypt        = true
