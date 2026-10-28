aws_account_id           = "844825014198"
region                   = "us-west-2"
environment              = "production"
state_bucket             = "rubber-duck-terraform-state-844825014198"
state_key                = "rubber-duck/environments/production/terraform.tfstate"
vpc_id                   = "vpc-0d5da450de7b3e1ee"
subnet_id                = "subnet-0a49a0288c57235e1"
availability_zone        = "us-west-2b"
ami_id                   = "ami-026ec9e84a2221297"
instance_type            = "t3.small"
ecr_repository_name      = "beanlab/rubber-duck"
configuration_bucket     = "rubber-duck-config"
permissions_boundary_arn = "arn:aws:iam::844825014198:policy/iamRolePermissionBoundary"
runtime_s3_prefixes = {
  byu-cms-metrics   = ["cs-merged-dashboard.csv"]
  stats121-datasets = ["datasets/*"]
}
ses_sender_identity = "byu-cs-course-ops@cs.byu.edu"
